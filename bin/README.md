## Start a dev env

### Setup

```sh
mkvirtualenv -a `my-dir` --system-site-packages coog # to have system pygtk
[cd `my-dir`]                                        # already there?
git clone coopengo/tryton                            # tryton fork
git clone coopengo/trytond                           # trytond fork
git clone coopengo/trytond-modules                   # trytond modules fork
git clone coopengo/coog                              # coog modules
./coog/bin/coog init bin                             # link bins
./coog/bin/coog init conf                            # copy conf
```

### Install

```sh
coog dep install               # install deps
coog mod link                  # link all available modules
```

### TODO
- logging params (hour -1)
- coog-mod + install module (with deps)
- coog-dep + purify deps list
- coog-wrk for workers (https://mmonit.com/monit/)
- coog-bat for batch management (http://python-rq.org/)
- coog-ts for timesheeting
    - coog ts add day hours project message # create entry
    - coog ts show d                        # print day (details)
    - coog ts show w                        # print week (per week day)
    - coog ts show m                        # print week (per month day)
