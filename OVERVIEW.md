# _Describe your application once_
![whiteboard](docs/img/whiteboard.jpg)

_... and let anyone deploy, manage, and scale it anywhere._

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

### Server, API, GUI, `git push`, etc...
The current suite of Checkmate tools consists of a command-line tool (CLI) called `pawn`, a server called `checkmate`, and an optional UI overlay to the API called `rook`.

The CLI should be able to operate by itself, but the server will be needed to share and manage state through a REST API for manipulating deployments. The API will support JSON and YAML interchangeably.

The server will use [SpiffWorkflow](https://github.com/knipknap/SpiffWorkflow) to orchestrate deployment operations. It will also provides *integrations* with:

- **git** (clone, push, pull):

    `git clone http://localhost:8080/deployments/fa4b67.git`

- **knife** if your app includes Chef cookbooks. Set your chef org URL to the deployment's URL and ...

   `knife node list`

