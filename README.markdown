Pastedown
=========

Pastedown is a pastebin service for [Markdown][] documents. It has following
features:

 - Fully-[Markdown][]-powered
 - Revision control
 - Forking
 - Slug auto-detection


  [markdown]: http://daringfireball.net/projects/markdown/


Requirements
------------

 - [Python][] 2.5
 - [Google App Engine][gae] Python SDK
 - Etc; read external_libs.txt also.


  [python]: http://www.python.org/
  [gae]: http://code.google.com/appengine/


Setup development environment
-----------------------------

In order to develop Pastedown, you should setup a development environment for
it first. Pastedown is a [Google App Engine][gae] application, so you should
install Google App Engine Python SDK in your working computer first.

Then, clone the repository of Pastedown from GitHub:

    $ git clone http://github.com/lunant/pastedown

There is a configuration file named `config.ini` in the working directory.
(The path is exactly `pastedown/config.ini`.) Open this file with your favorite
editor and fill following three fields:

    [vlaah]
    appkey = your_application_key_goes_here

    [recaptcha]
    public_key = your_public_key
    private_key = your_private_key


You can create a new [VLAAH][] application key from <http://api.vlaah.com/>.
Anyone can create new public key and private key pair of [reCAPTCHA][] in
their website if they have a Google account.

Lastly, you should resolve dependencies. Following command downloads depending
libraries automatically. (Google App Engine doesn't support [setuptools][],
[distribute][], [virtualenv][] or any other similar tools, so we should resolve
dependencies by ourself.)

    $ cd pastedown/
    pastedown$ python setup.py download_libs

It's finished. You can launch your Pastedown application in your working
computer on the Google App Engine development server -- [dev_appserver.py][].

    pastedown$ cd ..
    $ dev_appserver.py --port=9999 pastedown


  [vlaah]: http://www.vlaah.com/
  [recaptcha]: http://www.google.com/recaptcha
  [setuptools]: http://peak.telecommunity.com/DevCenter/setuptools
  [distribute]: http://packages.python.org/distribute/
  [virtualenv]: http://virtualenv.openplans.org/
  [dev_appserver.py]: http://bit.ly/gae-devserver


Author and license
------------------

Written by Hong MinHee <http://dahlia.kr/>.  
Copyright 2010 [Lunant][].  
The source code is available under [AGPL][].  


  [lunant]: http://lunant.net/
  [agpl]: http://www.gnu.org/licenses/agpl-3.0.html

