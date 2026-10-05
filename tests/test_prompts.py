"""Regression tests: load definitions only; never run the update entry point."""

import errno
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import subprocess
import tempfile
import textwrap
import time
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "aggiorna").read_text()
MARKER = "#== Cleanup:"
assert SOURCE.count(MARKER) == 1
DEFINITIONS = SOURCE.split(MARKER, 1)[0]
BASH = shutil.which("bash")


class PromptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="debbasedup-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("AGGIORNA_DEBUG", "BASH_ENV", "ENV", "SUDO_PID")
            and not key.startswith("BASH_FUNC_")
        }
        self.env.update(
            PATH=f"{self.bin}{os.pathsep}{os.defpath}",
            TMPDIR=str(self.root),
            TEST_ROOT=str(self.root),
            TERM="xterm-256color",
        )
        # Fail closed if any test accidentally reaches a real system command.
        for name in (
            "sudo", "apt-get", "apt", "dpkg", "dpkg-query", "flatpak", "curl",
            "systemctl", "cromup",
        ):
            self.command(
                name,
                'printf "FORBIDDEN: %s\\n" "$0" >> "$TEST_ROOT/forbidden"\nexit 97',
            )

    def tearDown(self):
        self.assertFalse((self.root / "forbidden").exists(),
                         "A test reached an unmocked system command")

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + textwrap.dedent(body) + "\n")
        path.chmod(0o700)
        return path

    def script(self, body):
        return DEFINITIONS + """
PROMPT_TICKS=2
QUIET_TICKS=5
""" + textwrap.dedent(body)

    def bash(self, body, input=""):
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", self.script(body)],
            input=input, capture_output=True, text=True, env=self.env, timeout=8,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def terminal(self, body, answers):
        """Reply through a real PTY only after each prompt becomes visible."""
        pid, master = pty.fork()
        if pid == 0:
            os.execve(BASH, [BASH, "--noprofile", "--norc", "-c",
                            self.script(body)], self.env)
        output = bytearray()
        answered = 0
        search_from = 0
        deadline = time.monotonic() + 8
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], 0.1)
                if not readable:
                    continue
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output.extend(chunk)
                if answered < len(answers):
                    prompt, reply = answers[answered]
                    pos = output.find(prompt.encode(), search_from)
                    if pos >= 0 and b"\x1b[?25h" in output[pos:]:
                        # No redraw may overwrite the visible question while
                        # the command waits; no answer should be synthesized.
                        readable, _, _ = select.select([master], [], [], 0.25)
                        if readable:
                            extra = os.read(master, 65536)
                            output.extend(extra)
                            self.fail(f"Output changed before answering: {extra!r}")
                        os.write(master, reply.encode())
                        answered += 1
                        search_from = len(output)
            else:
                self.fail(f"Terminal test timed out: {output.decode(errors='replace')}")
            _, status = os.waitpid(pid, 0)
            pid = None
            self.assertEqual(os.waitstatus_to_exitcode(status), 0,
                             output.decode(errors="replace"))
            self.assertEqual(answered, len(answers),
                             output.decode(errors="replace"))
            return output.decode(errors="replace")
        finally:
            if pid is not None:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            os.close(master)

    def test_recognizes_prompt_formats(self):
        prompts = [
            "Continue? [y/N]", "Perform operation? [Y|n]: ",
            "\x1b[33mContinue? [y/N]\x1b[0m", "Press ENTER to continue",
            "Premi INVIO per continuare", "PRESS RETURN", "Hit any key",
            "Premere il tasto INVIO", "Seleziona un'opzione:",
            "\x1b[2K\rChoose: ", "Choice: ", "Scelta: ", "Password:",
            "\x1b]8;;https://example.invalid\x1b\\Continue?\x1b]8;;\x1b\\",
            "\x1b]0;title\x07Continue?\x1b[0m\r",
        ]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.bash(f"is_question {shlex.quote(prompt)}")

    def test_progress_and_blank_lines_are_not_questions(self):
        for text in ("", "   ", "\x1b[0m", "Downloading 15%", "Resolving...",
                     "Running transaction", "[1/2] Updating package 100%"):
            with self.subTest(text=text):
                self.bash(f"! is_question {shlex.quote(text)}")

    def test_normalizes_redraws_and_ignores_blank_lines(self):
        output = self.bash(r"""
            text=$'Downloading 10%\r\e[2KPremi INVIO\e[0m\r'
            clean_prompt_line text
            printf '%s\n' "$text"
            last_line=''
            remember_prompt_line $'\e[33mContinue? [y/N]\e[0m' last_line
            remember_prompt_line '' last_line
            remember_prompt_line $' \e[0m\r' last_line
            printf '%s\n' "$last_line"
            remember_prompt_line 'Downloading 15%' last_line
            printf '%s\n' "$last_line"
        """)
        self.assertEqual(output.splitlines(),
                         ["Premi INVIO", "Continue? [y/N]", "Downloading 15%"])

    def test_partial_prompt_keeps_context_without_duplicate_display(self):
        output = self.bash(r"""
            log=$TEST_ROOT/context.log
            printf 'Warning: keep the device connected\n' > "$log"
            pending='Continue? [y/N] '; stall=0; asking=0; last_line=''
            poll_prompt Test pending stall asking last_line "$log"
            (( asking == 0 )) || exit 1
            poll_prompt Test pending stall asking last_line "$log"
            (( asking == 1 )) || exit 2
            [[ -z $pending ]] || exit 3
            [[ $(wc -l < "$log") == 2 ]] || exit 4
            poll_prompt Test pending stall asking last_line "$log"
        """)
        self.assertIn("Warning: keep the device connected", output)
        self.assertIn("Continue? [y/N]", output)
        self.assertEqual(output.count("the command is asking:"), 1)
        self.assertIn("\a", output)          # una domanda vera si deve sentire

    def test_fallback_shows_unknown_menu_without_assuming_a_question(self):
        output = self.bash(r"""
            log=$TEST_ROOT/menu.log
            printf 'Choose a provider\n  1. Alpha\n  2. Beta\n' > "$log"
            pending=''; stall=0; asking=0; last_line='  2. Beta'
            for ((n=1; n<QUIET_TICKS; n++)); do
                poll_prompt Test pending stall asking last_line "$log"
                (( asking == 0 )) || exit 1
            done
            poll_prompt Test pending stall asking last_line "$log"
            (( asking == 1 ))
        """)
        for text in ("Choose a provider", "1. Alpha", "2. Beta", "otherwise wait"):
            self.assertIn(text, output)
        self.assertNotIn("the command is asking:", output)
        # un comando lento ma sano non deve suonare come un allarme
        self.assertNotIn("\a", output)

    def test_silent_command_fallback_leaves_stdin_untouched(self):
        output = self.bash(r"""
            pending=''; stall=$(( QUIET_TICKS - 1 )); asking=0; last_line=''
            poll_prompt Test pending stall asking last_line /dev/null
            IFS= read -r answer
            [[ $answer == untouched ]]
        """, input="untouched\n")
        self.assertIn("no output available yet", output)

    def test_display_removes_captured_terminal_controls(self):
        output = self.bash(r"""
            ask_begin Test $'\e[2J\e[HWarning\n\e[33mContinue? [y/N]\e[0m\n\n'
        """)
        self.assertIn("Warning", output)
        self.assertIn("Continue? [y/N]", output)
        self.assertNotIn("\x1b[2J", output)
        self.assertNotIn("\x1b[H", output)
        self.assertNotIn("\x1b[33m", output)

    def test_run_step_handles_colored_enter_prompt_and_function_hook(self):
        output = self.terminal(r"""
            mock_hook() {
                printf '\e[33mPremi INVIO per continuare\e[0m\n\n'
                IFS= read -r answer
                printf 'ANSWER=<%s>\n' "$answer" >> "$TEST_ROOT/answers"
            }
            run_step Test-step mock_hook
            (( steps_ok == 1 && steps_fail == 0 ))
        """, [("Premi INVIO per continuare", "\n")])
        self.assertIn("the command is asking:", output)
        self.assertIn("ANSWER=<>", (self.root / "answers").read_text())

    def test_run_step_external_hook_and_menu_fallback(self):
        self.command("mock-hook", """
            printf 'Choose a provider\\n  1. Alpha\\n  2. Beta\\n'
            IFS= read -r answer
            printf 'ANSWER=<%s>\\n' "$answer" >> "$TEST_ROOT/answers"
        """)
        output = self.terminal("""
            run_step Test-menu mock-hook
            (( steps_ok == 1 && steps_fail == 0 ))
        """, [("2. Beta", "2\n")])
        self.assertIn("otherwise wait", output)
        self.assertIn("ANSWER=<2>", (self.root / "answers").read_text())

    def test_apt_conffile_prompt_on_stderr(self):
        """Il conffile di dpkg esce su stderr, che run_apt manda nel log e non
        nella pipe: se il rilevatore guarda solo la pipe, la domanda non si vede
        mai. DEBIAN_FRONTEND=noninteractive zittisce debconf, non questa."""
        self.command("mock-apt", r"""
            printf 'pmstatus:base-files:10:Unpacking\n'
            printf 'Configuration file /etc/foo.conf\n' >&2
            printf '  ==> Modified (by you or by a script) since installation.\n' >&2
            printf '  ==> Package distributor has shipped an updated version.\n' >&2
            printf '*** foo.conf (Y/I/N/O/D/Z) [default=N] ? ' >&2
            IFS= read -r answer
            printf 'ANSWER=<%s>\n' "$answer" >> "$TEST_ROOT/answers"
            printf 'pmstatus:base-files:100:Done\n'
        """)
        output = self.terminal("""
            run_apt Test-conffile Install 1 0 300 300 1000 mock-apt
            (( steps_ok == 1 && steps_fail == 0 ))
        """, [("(Y/I/N/O/D/Z)", "N\n")])
        self.assertIn("the command is asking:", output)
        # le opzioni stanno nelle righe sopra la domanda: senza contesto non si
        # puo' rispondere
        self.assertIn("Package distributor has shipped an updated version", output)
        self.assertIn("ANSWER=<N>", (self.root / "answers").read_text())

    def test_apt_partial_prompt_on_the_pipe(self):
        """Domanda lasciata a meta' riga sullo stdout, che finisce nella pipe."""
        self.command("mock-apt", r"""
            printf 'dlstatus:1:10:Getting file\n'
            printf '\033[33mDo you want to continue? [Y/n]\033[0m '
            IFS= read -r answer
            printf 'ANSWER=<%s>\n' "$answer" >> "$TEST_ROOT/answers"
            printf 'pmstatus:base-files:100:Done\n'
        """)
        output = self.terminal("""
            run_apt Test-pipe Install 1 0 300 300 1000 mock-apt
            (( steps_ok == 1 && steps_fail == 0 ))
        """, [("Do you want to continue? [Y/n]", "y\n")])
        self.assertIn("the command is asking:", output)
        self.assertIn("ANSWER=<y>", (self.root / "answers").read_text())

    def test_apt_progress_resumes_after_the_answer(self):
        self.command("mock-apt", r"""
            printf 'Do you want to continue? [Y/n] '
            IFS= read -r answer
            printf 'pmstatus:base-files:50:Unpacking base-files\n'
            printf 'pmstatus:base-files:100:Done\n'
        """)
        output = self.terminal("""
            run_apt Test-progress Install 1 0 300 300 1000 mock-apt
            (( steps_ok == 1 && steps_fail == 0 ))
        """, [("Do you want to continue? [Y/n]", "y\n")])
        self.assertIn("Install 100%", output)

    def test_flatpak_update_and_remove_prompts(self):
        self.command("flatpak", r"""
            printf '\033[33mPress ENTER to continue\033[0m\n\n'
            IFS= read -r answer
            printf 'ANSWER=<%s>\n' "$answer" >> "$TEST_ROOT/answers"
            printf '100%%\n'
        """)
        for mode in ("update", "remove"):
            with self.subTest(mode=mode):
                self.terminal(f"""
                    run_flatpak Test-flatpak {mode} 0 1000 org.example.Mock
                    (( steps_ok == 1 && steps_fail == 0 ))
                """, [("Press ENTER to continue", "\n")])
        self.assertEqual(
            (self.root / "answers").read_text().count("ANSWER=<>"), 2)

    def test_failed_commands_remain_failed(self):
        # "mock failure" non somiglia a uno stato rotto: apt_looks_broken deve
        # restare zitto, o il test finirebbe dentro la riparazione automatica.
        self.command("mock-fail", "printf 'mock failure\\n' >&2\nexit 7")
        self.bash("""
            run_step Test-fail mock-fail
            run_apt Test-apt-fail Install 1 0 300 300 1000 mock-fail
            (( steps_ok == 0 && steps_fail == 2 ))
        """)

    def test_flatpak_delta_retry(self):
        """Flathub manda delta statici fuori misura e il pull muore a meta': quel
        ref va rilanciato con --no-static-deltas, una volta sola."""
        self.command("flatpak", """
            printf '%s\\n' "$*" >> "$TEST_ROOT/flatpak-args"
            if [[ $* != *--no-static-deltas* ]]; then
                printf 'Decompressed delta part exceeds configured limit\\n'
                exit 1
            fi
            printf '100%%\\n'
        """)
        self.bash("""
            run_flatpak Test-delta update 0 1000 org.example.Mock
            (( steps_ok == 1 && steps_fail == 0 ))
        """)
        args = (self.root / "flatpak-args").read_text().splitlines()
        self.assertEqual(len(args), 2, args)
        self.assertNotIn("--no-static-deltas", args[0])
        self.assertIn("--no-static-deltas", args[1])

    def test_reboot_reason_from_a_newer_kernel(self):
        self.command("dpkg-query", r"""
            printf 'linux-image-99.0.0-1-amd64\n'
        """)
        output = self.bash("""
            detect_reboot_needed || true
            printf '%s\\n' "${REBOOT_REASONS[@]}"
        """)
        self.assertIn("new kernel installed: 99.0.0-1-amd64", output)

    def test_no_reboot_reason_when_the_running_kernel_is_the_newest(self):
        """Un avviso di riavvio che compare sempre e' un avviso che si impara a
        ignorare: qui il kernel installato e' quello in esecuzione."""
        self.command("dpkg-query", r"""
            printf 'linux-image-%s\n' "$(uname -r)"
        """)
        output = self.bash("""
            detect_reboot_needed || true
            printf '%s\\n' "${REBOOT_REASONS[@]}"
        """)
        self.assertNotIn("new kernel installed", output)

    def test_debug_diary_records_every_step(self):
        """Senza diario, di uno stallo non resta traccia: e' cosi' che su Fedora
        era rimasto invisibile per settimane."""
        self.command("mock-hook", "printf 'output del passo\\n'")
        self.bash("""
            DEBUG_DIR=$TEST_ROOT/diario
            mkdir -p "$DEBUG_DIR"
            run_step Test-diario mock-hook
            (( steps_ok == 1 ))
        """)
        diary = (self.root / "diario" / "diario.txt").read_text()
        self.assertIn("inizio: Test-diario", diary)
        self.assertIn("fine:   Test-diario", diary)
        # l'output del passo, che di norma viene buttato, qui resta
        kept = (self.root / "diario" / "Test-diario.log").read_text()
        self.assertIn("output del passo", kept)

    def test_script_questions_never_use_read_p(self):
        """`read -p` stampa il prompt solo se il *suo* stdin e' un terminale, e
        lo manda su stderr: con lo stdin su una pipe la domanda sparisce mentre
        il read continua ad aspettare. Qui lo stdout e' una pipe e la domanda
        deve comparire lo stesso."""
        code = "\n".join(l for l in DEFINITIONS.splitlines()
                         if not l.lstrip().startswith("#"))
        for forbidden in ("read -r -p", "read -p"):
            self.assertNotIn(forbidden, code,
                             f"{forbidden} e' tornato in un prompt dello script")
        output = self.bash("""
            ask_yes_no "Accetti e vuoi continuare?" && echo SI || echo NO
        """, input="y\n")
        self.assertIn("Accetti e vuoi continuare?", output)
        self.assertIn("SI", output)

    def test_flatpak_update_list_survives_a_new_runtime(self):
        """Quando un'app passa a un runtime non ancora installato, `flatpak
        update` prima di elencare qualsiasi cosa chiede se installarlo; in fase
        di sola lettura nessuno risponde e l'elenco intero viene abortito. Visto
        sul campo sul gemello Fedora il 12 set 2026: KTorrent chiedeva
        org.kde.Platform 6.11 e il passo diceva "nothing to do", verde, con
        dodici aggiornamenti in coda. Flatpak e' lo stesso di qua e di la'."""
        self.command("flatpak", r"""
            if [[ $1 == remote-ls ]]; then
                printf 'app/com.brave.Browser/x86_64/stable
'
                printf 'app/org.kde.ktorrent/x86_64/stable
'
                printf 'runtime/org.kde.Platform/x86_64/6.10
'
                printf 'app/com.brave.Browser/x86_64/stable
'   # doppione: un ref in due remoti
                exit 0
            fi
            # la via che faceva domande: nessuno risponde, l'elenco muore qui
            printf 'Required runtime for org.kde.ktorrent/x86_64/stable found in remote flathub
'
            printf 'Do you want to install it? [Y/n]: '
            IFS= read -r _answer
            printf 'error: requires the runtime org.kde.Platform/x86_64/6.11
' >&2
            exit 1
        """)
        output = self.bash("""
            flatpak_refs update
            printf 'LABEL=<%s>\n' "$(ref_label runtime/org.kde.Platform/x86_64/6.10)"
            printf 'LABEL=<%s>\n' "$(ref_label app/com.brave.Browser/x86_64/stable)"
        """)
        self.assertEqual(
            [line for line in output.splitlines() if not line.startswith("LABEL=")],
            ["app/com.brave.Browser/x86_64/stable",
             "app/org.kde.ktorrent/x86_64/stable",
             "runtime/org.kde.Platform/x86_64/6.10"])
        self.assertIn("LABEL=<org.kde.Platform 6.10>", output)
        self.assertIn("LABEL=<com.brave.Browser>", output)

    def test_flatpak_update_list_includes_end_of_life_runtimes(self):
        """Senza `--all` remote-ls nasconde i ref a fine vita, che pero'
        continuano a ricevere commit. Il caso reale, sul gemello Fedora
        (5 ott 2026): Discover mostrava freedesktop Platform 24.08 e i suoi
        GL.default, `aggiorna` no. Con `--all` arrivano anche le estensioni,
        che vanno scartate."""
        self.command("flatpak", r"""
            [[ $1 == remote-ls ]] || exit 1
            printf 'app/com.brave.Browser/x86_64/stable\n'
            if [[ " $* " == *" --all "* || " $* " == *" -a "* ]]; then
                printf 'runtime/org.freedesktop.Platform.GL.default/x86_64/24.08\n'
                printf 'runtime/org.freedesktop.Platform.Locale/x86_64/24.08\n'
                printf 'runtime/org.freedesktop.Platform/x86_64/24.08\n'
                printf 'runtime/org.freedesktop.Platform.Debug/x86_64/24.08\n'
                printf 'runtime/com.brave.Browser.Locale/x86_64/stable\n'
            fi
        """)
        output = self.bash("flatpak_refs update")
        self.assertEqual(
            output.splitlines(),
            ["app/com.brave.Browser/x86_64/stable",
             "runtime/org.freedesktop.Platform.GL.default/x86_64/24.08",
             "runtime/org.freedesktop.Platform/x86_64/24.08"])

    def test_main_apt_calls_keep_command_argument_positions(self):
        prefix = ('sudo -n "${UNBUF[@]}" env LC_ALL=C '
                  'DEBIAN_FRONTEND=noninteractive apt-get -y -q '
                  '-o Dpkg::Use-Pty=0 ')
        calls = [l.strip() for l in SOURCE.splitlines() if l.strip().startswith(prefix)]
        self.assertEqual(len(calls), 2, calls)
        self.assertTrue(calls[0].endswith("full-upgrade"), calls[0])
        self.assertTrue(calls[1].endswith("autoremove"), calls[1])
        # nessun sudo catturato senza -n: chiederebbe la password sotto la
        # pipeline, su /dev/tty, fuori dal log e sotto il disegno
        leftovers = [l.strip() for l in SOURCE.splitlines()
                     if "sudo env" in l and not l.lstrip().startswith("#")]
        self.assertEqual(leftovers, [])

    def test_self_update_curl_has_timeouts(self):
        """Nella zona muta dopo l'ultimo nodo non si muove piu' niente: un
        mirror che non risponde lascerebbe curl appeso senza spiegazioni."""
        line = next(l for l in SOURCE.splitlines() if "curl -fsSL" in l)
        self.assertIn("--connect-timeout", line)
        self.assertIn("--max-time", line)

if __name__ == "__main__":
    unittest.main()
