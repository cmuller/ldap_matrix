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
---
#here set flags for users based on LDAP Group memberships:
ldapgroups-forbidroomcreation:
   - ldapgroup1
   - ldapgroup2
ldapgroups-forbidencryptedroomcreation:
   - ldapgroup1
ldapgroups-forbidunencryptedroomcreation:
   - ldapgroup2
---

- matrixgroup: +group1:domain.com
  rooms:
    - room1 or space1
    - room2 or space2
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
* for each matrix group, either a list of individual members and a list of LDAP groups can be specified (*ldapusers*)
* all these users in that *matrixgroup are enrolled to the set of rooms or spaces in that matrixgroup. 
* In the template above there is no equivalent to +group1:domain.com, since now matrix handles spaces and rooms the same way
* 
* in the *restricted* section you can set for each room a seperate specific list of users or ldapgroups that have access to that room.
 It doesn't matter, if that room belongs to another space or not.

For the members of *ldapgroups-forbidroomcreation* and *ldapgroups-forbidroomcreation* a flag is created in the policy that forbids the room-creation for those users.

## Caveats

* neither spaces nor rooms are *created* by this script: they need to be create beforehand by an adminaccount and corporal enabled on your Matrix server
* also rooms have to be inserted in their relevant spaces beforehand
* this script is generating a corporal `policy.json` file that you can either *push* or place in a policy provider (see https://github.com/devture/matrix-corporal/blob/master/docs/policy-providers.md for more details).

