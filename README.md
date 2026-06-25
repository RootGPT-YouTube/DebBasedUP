# DebBasedUP
Uno script per aggiornare e manutenere la propria distro basata su Debian (NON immutabile)  
Copia e incolla nel terminale il comando sottostante (accertati di essere nella home del tuo account):  
`curl -sSL https://raw.githubusercontent.com/RootGPT-YouTube/DebBasedUP/main/install | bash`  
Adesso avrai un comando nuovo nel terminale - `aggiorna` - che quando lo lancerai aggiornerà tutte le app installate con APT e FLATPAK e farà anche pulizia dei file e dipendenze obsolete.

## Interfaccia
`aggiorna` ha un'interfaccia originale, pensata per essere chiara e gradevole nel terminale:

- **Header a gradiente truecolor** con il titolo del progetto.
- **Pipeline verticale**: ogni operazione è un nodo collegato (`●` completato, `✗` fallito) con uno spinner ad arco rotante e un timer mentre è in corso.
- **Output pulito**: l'output dei comandi è nascosto durante l'esecuzione e mostrato in un riquadro **solo in caso di errore**.
- **Scheda di resoconto** finale con operazioni riuscite, tempo impiegato, spazio liberato su disco ed esito dell'autoaggiornamento dello script.

Operazioni eseguite: `apt-get update`, `apt-get full-upgrade`, `apt-get autoremove`, `flatpak update`, `flatpak uninstall --unused`, l'hook opzionale `cromup` (se presente) e l'autoaggiornamento dello script stesso.
