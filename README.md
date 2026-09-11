# DebBasedUP
Uno script per aggiornare e manutenere la propria distro basata su Debian (NON immutabile)  
Copia e incolla nel terminale il comando sottostante (accertati di essere nella home del tuo account):  
`curl -sSL https://raw.githubusercontent.com/RootGPT-YouTube/DebBasedUP/main/install | bash`  
Adesso avrai un comando nuovo nel terminale - `aggiorna` - che quando lo lancerai aggiornerà tutte le app installate con APT e FLATPAK e farà anche pulizia dei file e dipendenze obsolete.

## ⚠️ Avviso di responsabilità — leggi prima di usarlo

**AGGIORNA** esegue una sequenza di comandi di sistema (`apt-get`, `flatpak`) per aggiornare la tua distribuzione basata su Debian.

Sono operazioni che modificano il sistema in profondità: un `full-upgrade` può rimuovere pacchetti per risolvere le dipendenze, e un aggiornamento interrotto o un pacchetto difettoso possono lasciare il sistema instabile o non avviabile.

AGGIORNA è distribuito **senza alcuna garanzia**, come previsto dalle sezioni 15 e 16 della licenza [GNU GPL v3](LICENSE). **L'autore non risponde di danni, perdita di dati o sistemi resi inutilizzabili** derivanti dall'uso dello script.

**Usando AGGIORNA lo fai a tuo rischio e ti assumi la piena responsabilità delle modifiche apportate al tuo sistema.** Se hai dati importanti, fai un backup prima di procedere.

Lo stesso avviso compare all'avvio del comando, prima ancora che venga chiesta la password, e richiede una conferma esplicita: qualunque risposta diversa da `y`/`s` fa uscire lo script **senza modificare nulla**.

## Interfaccia
`aggiorna` ha un'interfaccia originale, pensata per essere chiara e gradevole nel terminale:

- **Header a gradiente truecolor** con il titolo del progetto.
- **Pipeline verticale**: ogni operazione è un nodo collegato (`●` completato, `✗` fallito) con uno spinner ad arco rotante e un timer mentre è in corso.
- **Output pulito**: l'output dei comandi è normalmente nascosto durante l'esecuzione; viene mostrato in caso di errore, di domanda o di silenzio prolungato.
- **Domande interattive**: le domande riconosciute vengono mostrate dopo circa 2 secondi, insieme all'output recente. Conta soprattutto per i **prompt di dpkg sui file di configurazione**: `DEBIAN_FRONTEND=noninteractive` zittisce debconf ma non dpkg, che per un conffile modificato chiede lo stesso e aspetta — e quella domanda esce su *stderr*, non sul canale da cui arriva l'avanzamento. Il riquadro mostra anche le righe precedenti, dove stanno le opzioni (`Y/I/N/O/D/Z`): da sola l'ultima riga non basta per rispondere. Il rilevatore ignora colori e controlli del terminale, conserva la domanda anche se seguono righe vuote e riconosce anche «Press ENTER»/«Premi INVIO». Se dopo circa 45 secondi non arriva nuovo output viene mostrato comunque il contesto recente, in silenzio (il campanello suona solo per le domande vere): un comando lento non è necessariamente bloccato, quindi **rispondi solo se c'è una richiesta esplicita, altrimenti attendi**. Nessuna risposta viene inviata automaticamente. Le domande poste dallo script stesso vengono stampate direttamente, senza `read -p`, e la risposta viene letta dal terminale.
- **Autenticazione**: la password viene chiesta all'inizio; i comandi privilegiati usano `sudo -n`, così un'eventuale scadenza delle credenziali non apre una richiesta di password nascosta sotto il disegno della pipeline.
- **Scheda di resoconto** finale con operazioni riuscite, tempo impiegato, spazio liberato su disco ed esito dell'autoaggiornamento dello script.

## Test locali

`bash -n aggiorna && bash -n install` controlla la sintassi degli script.
`python3 -m unittest discover -s tests -v` verifica il rilevamento e la visualizzazione delle domande con comandi simulati, senza aggiornare il sistema o richiedere privilegi.

Operazioni eseguite: `apt-get update`, `apt-get full-upgrade`, `apt-get autoremove`, `flatpak update`, `flatpak uninstall --unused`, l'hook opzionale `cromup` (se presente) e l'autoaggiornamento dello script stesso.
