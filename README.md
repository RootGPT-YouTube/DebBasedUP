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
- **Output pulito**: l'output dei comandi è nascosto durante l'esecuzione e mostrato in un riquadro **solo in caso di errore**.
- **Domande interattive**: se un comando fa una domanda nel terminale (es. un prompt di dpkg su un file di configurazione), lo script se ne accorge, la mostra in un riquadro dedicato e ti passa la tastiera — la risposta digitata arriva direttamente al comando, poi la pipeline riprende.
- **Scheda di resoconto** finale con operazioni riuscite, tempo impiegato, spazio liberato su disco ed esito dell'autoaggiornamento dello script.

Operazioni eseguite: `apt-get update`, `apt-get full-upgrade`, `apt-get autoremove`, `flatpak update`, `flatpak uninstall --unused`, l'hook opzionale `cromup` (se presente) e l'autoaggiornamento dello script stesso.
