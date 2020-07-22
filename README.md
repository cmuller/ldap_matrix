# Matrix Corporal Policy Specification Using LDAP Groups

Generates a Matrix Corporal JSON policy file with data coming from:
- an LDAP server in which groups are specified containing `memberUid` entries, and
- a YAML file in which a specification of which users must join which communities and/or rooms.

## Install with Pipenv

* install `pipenv` tool as a user (https://pipenv.pypa.io)
* `$ export PATH=$HOME/.local/bin/:$PATH`
* `$ pipenv sync`
* `$ pipenv shell`

## Install with Pip (not recommended)

* Python >= 3.6
* `pip install -r requirements.txt`

## Usage

* This scripts takes as input a specification in the form of a YAML file
* and generates a so-called *Policy* file for Matrix Corporal reconciliator tool (see https://github.com/devture/matrix-corporal/blob/master/docs/policy.md)
* first of all you need to:
   * configure in `$HOME/.ldapsync.cfg` your server credentials (see `ldapsync.cfg` as example)
   * change (at least) DOMAIN and LDAP_SEARCH_BASE (potentially LDAP filters also) in `spec2policy.py`
* then to generate the policy file, type: `$ ./spec2policy.py matrix.yml policy.json`
* and finally to push the policy, type `$ curl -s --insecure -XPUT --data "@$(pwd)/policy.json" -H 'Authorization: Bearer ......' https://matrix.domain.com/_matrix/corporal/policy | jq .`
* also to automate the build and deployment of the policy file, it is possible to use a CI tool such as Jenkins, Gitlab CI, Travis CI etc. See the `.gitlab-ci.yml` as an example (it requires the definition of the credentials in a protected $CFG environment variable).

## Input specification format

~~~
- matrixgroup: +group1:domain.com
  rooms:
    - room1
    - room2
  ldapgroups:
    - ldapgroup1
    - ldapgroup2
  ldapusers:
    - supplementaryuser1
    - supplementaryuser2
  restricted:
    - room: room3
      groups:
        - ldapgroup3
        - ldapgroup4
      users:
        - supplementaryuser1
        - supplementaryuser3
~~~

* a list of *matrixgroup* can be specified, each in its own section
* for each matrix group, either a list of individual members is specified (*ldapusers*)
* or a list of members belonging to LDAP groups is specified (*ldapgroups*)
* or both
* also a *restricted* section can add rooms for which those specified members above do not have access. For each of these restricted rooms, there is a specific room-only member list, i.e., for each room a *users* or a *groups* list or both.

## Caveats

* neither matrix groups (aka communities) nor rooms are *created* by this script: they need to be create beforehand and corporal enabled on your Matrix server
* also rooms have to be inserted in their relevant Matrix group beforehand
* this script is generating a corporal `policy.json` file that you can either *push* or place in a policy provider (see https://github.com/devture/matrix-corporal/blob/master/docs/policy-providers.md for more details).

