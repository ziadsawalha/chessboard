#Checkmate
##Code Deployment for Humans

### _Describe your application once..._
![whiteboard](docs/img/whiteboard.jpg)

_... and let anyone deploy, manage, and scale it anywhere using the tools they prefer._

####Focus on code

There are many configuration management tools out there; Chef, Puppet, Salt, Docker, Vagrant, etc..., but **keeping up with all of them is a distraction** from writing awesome code.

Checkmate takes all of the work out of learning these tools and let's us describe how our code is installed, how to run it, and what it needs.

##How easy is it?

Install checkmate and describe your application using the `app` command:

```console:

    $ app exposes http
      blueprint.yaml created. Commit and push it to share it with others.
    $ app requires mongodb
      blueprint.yaml updated.
    $ app requires python --version ">=2.7.1,<3"
      blueprint.yaml updated.
    $ app supports debian --packages python-dev,git
    blueprint.yaml updated.
    $ app supports osx
    blueprint.yaml updated.
    $ app supports memcache --set-env CACHE_PORT=MEMCACHE_PORT,USE_CACHE=1
    blueprint.yaml updated.
    $ app define --start-command="bin/my_app START --eventlet --port HTTP_PORT"
    blueprint.yaml updated.
    $ app show definition
	components:
	  app:
	    provides:
	    - application: http[8080?]
	      exposed: true
	      set_env:
	      - HTTP_PORT: options://port
	    requires:
	    - database: mongo
	    - runtime: python
	      version: '>=2.7.1,<3'
	    supports:
	    - cache: memcache
	      set_env:
	      - CACHE_PORT: MEMCACHE_PORT
	      - USE_CACHE: '1'
	    - compute:
	        from:
	        - debian:
	            packages: [python-dev, git]
	        - osx
	    commands:
	      start: 'bin/checkmate START —eventlet —port HTTP_PORT'
```

Let's run an instance of our app in Docker:

    $ app deploy --providers=docker
    Deployed from master@d9520bba.
    Browse to http://192.168.59.103:31654
    RESOURCE ID   ROLE     IMAGE         CREATED        STATUS        PORTS
    docker:5f6ae  mongodb  mongo:latest  6 seconds ago  Up 4 seconds  27017/tcp 
    docker:4f44e  app      app:latest    7 seconds ago  Up 3 seconds  31654/tcp  

Let's run an instance of our app on Rackspace:

    $ app deploy --providers=core,rackspace --region=dfw --username=me --api-key=$API_KEY
    Deployed from master@d9520bba.
    Browse to http://173.12.56.205
    RESOURCE ID       ROLE     TYPE    ADDRESS        CREATED         STATUS
    rax:dwf:d5223afa  mongodb  server  173.12.56.205  12 seconds ago  Up 4 seconds 
    rax:dfw:ffefc5c2  app      server  173.12.54.18   11 seconds ago  Up 2 seconds 

Let's manage our deployments:

    $ app list deployments
    ID       FROM             URL                          CREATED     STATUS
    5dff3e1  master@d9520bba  http://192.168.59.103:31654  2 days ago  Up 3 hours
    cc53228  master@d9520bba  http://173.12.56.205         2 days ago  Up 2 days

    $ app destroy 5dff3e1 --force
    5dff3e1 destroyed (two resources deleted)


## Overview of Checkmate
Checkmate gives you a simple way to **describe your application**; how to run it and which servers it needs. Using that definition, Checkmate tools can be used to **install and run your application anywhere** using a single command.

The same Checkmate definition can be used to launch your code on:

- Docker (or Vagrant)

    `pawn deploy --provider=docker`

   > `pawn` is the command-line tool

<!-- removed as a first-hand use case, but maintaining as a good architecture test with a valid use case (those of us who practice the dispicable coding practice of running things locally)
- a Mac OSX or Linux machine for hacking

    `pawn deploy --provider=local`

  <small>_...if you don't want virtualization between you and your running code_</small>
-->

- the Rackspace Public Cloud

    `pawn deploy --provider=rackspace --use-env-credentials`

- an OpenStack Cloud, AWS and other providers to come...

    `pawn deploy --provider=openstack --use-env-credentials`


### The "blueprint" File
You can store the definition of your application in a file called `blueprint` in your code respository to allow anyone to deploy and manage your code.

    git clone https://github.com/sauce/awesome
    cd awesome
    pawn deploy --provider=local  # or docker, vagrant, rackspace, aws


#### Example

Here is a sample `blueprint` in [YAML](http://yaml.org/) for our [sample app](examples/hello-world) (you can add a `.yaml` or `.json` extension to the file as a syntax hint to editors):

```yaml
components:
  web:
    description: A simple app for demonstration purposes
    commands:
      start: python hello.py $APP_PORT
    requires:
    - runtime: python>=2.5  # includes wsgiref
    provides:
    - application: http

```

 While you can put a `blueprint` file in your code repo to describe the application in that repo, you can also have a `blueprint` file that references **any repository** by URL or **well-known software** like MySQL or Wordpress. A `blueprint` file may also be used to just save your desired **topology** and configurations to re-use, version control, or share with others:

```yaml
topology:
  services:
    lb:
      component:
        type: load-balancer
        interface: http
      relations:
      - web: http
    web:
      component:
         name: wordpress
      relations:
      - db: mysql
    db:
      component:
        type: database
        interface: mysql
      constraints:
        - flavor: percona
        - version: "5.6"
        - max_allowed_packet: 268435456 # 256M

```

More complex blueprint examples are available in the [checkmate-blueprints](https://github.com/checkmate-blueprints) org on github.

