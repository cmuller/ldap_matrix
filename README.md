# Matrix Corporal Policy Specification Using LDAP Groups
 
* This scripts takes as input a specification in the form of a YAML file  and generates a so-called *Policy* file for Matrix Corporal reconciliator tool (see https://github.com/devture/matrix-corporal/blob/master/docs/policy.md) with data coming from an LDAP server in which groups are specified containing `memberUid` entries.
* It also generates any rooms and spaces mentioned in the yaml file, that do not exist on the Synapse Homeserver yet.


## Install with Pipenv

* install `pipenv` tool as a user (https://pipenv.pypa.io)
* `$ export PATH=$HOME/.local/bin/:$PATH`
* `$ pipenv sync`
* `$ pipenv shell`
* `$pipenv run ./spec2policy input.yml policy.json`

## Install with Pip (not recommended)

* Python >= 3.6
* `pip install -r requirements.txt`


## Configuration
   * configure in `$HOME/.ldapsync.cfg` your server credentials (see `ldapsync.cfg` as example)
   * change (at least) DOMAIN and LDAP_SEARCH_BASE (potentially LDAP filters also) in `spec2policy.py`
   * If the shared secret provider is installed on the HomeServer, you can
     For the room creation process to work it is recommended to access the homeserver directly thru port 8008 and not through matrix-corporal
## Usage
*  To generate the policy file, type: `$ ./spec2policy.py input.yml policy.json`
*  to push the policy to matrix-corporal, type `$ curl -s --insecure -XPUT --data "@$(pwd)/policy.json" -H 'Authorization: Bearer ......' https://matrix.domain.com/_matrix/corporal/policy | jq .`
* also to automate the build and deployment of the policy file, it is possible to use a CI tool such as Jenkins, Gitlab CI, Travis CI etc. See the `.gitlab-ci.yml` as an example (it requires the definition of the credentials in a protected $CFG environment variable).

## Input specification format

~~~
---
#here set flags on user level based on LDAP Group memberships:
ldapgroups-forbidroomcreation:
   - ldapgroup1
   - ldapgroup2
ldapgroups-forbidencryptedroomcreation:
   - ldapgroup1
ldapgroups-forbidunencryptedroomcreation:
   - ldapgroup2
---
#list of spaces and rooms. Rooms can be attached to a space with setting the entry childof
- space: SpaceName
  ldapgroups:
    - ldapgroup1
    - ldapgroup2
  ldapusers:
    - supplementaryuser1
    - supplementaryuser2
 - room: Roomname
   ldapgroups:
    - ldapgroup1
   ldapusers:
    - ldapuser1
   childof: SpaceName 
~~~

* On the first part of the yaml file, set the user based flags for the members of *ldapgroups-forbidroomcreation* and *ldapgroups-forbidencryptedroomcreation* and *forbidunencryptedroomcreation*.

* On the second part, list all spaces/rooms with their ldapgroups, individual ldapusers and with *childof* the parent space of each room, tha tu want to place in a space. 
All the rooms and spaces are created as private rooms by default. This can be adjusted by modifying the appropriate functions in spec2policy.py 


## Caveats

* There is no room deletion implemented. To delete rooms, use the synapse admin gui, for instance.
* A Matrix Administrator Account has to be enrolled in all of the room. This is necessary for the conciliation of matrix-corporal to work.

## Future ideas:
* implement hooks
* set room-powerlevels by ldapgroup-membership

