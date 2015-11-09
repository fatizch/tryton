# Workers management

This is a toolkit to deploy and monitor Coog with many workers.

## Modifiable files

- trytond.conf: same as usual with a variable for JSON\_RPC port
- logging.conf: same as usual with a variable for file path
- nginx.conf: an explained nginx conf file adapted to Coog
- redis.conf: small modifications to default redis conf (no persistence)
- config: "sourceable" script to set some variables
    - WORKERS: number of workers (defaut is nproc result)
    - WORKERS\_DIR: a folder to handle generated confs, pid and out files
    - JSON\_PORT: to be used by workers as n+1, n+2, n+3, ...
    - DB\_NAME: to be passed to trytond command line (optional)

## Non modifiable scripts

- coogw: all bash logic implemented there
- start/stop/restart:
    - called without params: start/stop/restart all workers
    - called with param (n): start/stop/restart worker n
- info: gives informations about workers (running, memory usage, time, ...).
  parameter is the rank of the worker

