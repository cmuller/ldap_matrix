#!/usr/bin/env python3

# Copyright (C) 2020 Wyplay, All Rights Reserved.

# This file is part of ldap_matrix
#
# ldap_matrix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# ldap_matrix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; see file COPYING.
# If not, see <http://www.gnu.org/licenses/>.
#

import os
import argparse
import configparser
import requests
import yaml
from ldap3 import Server, Connection, ALL
import json

# config and arguments parsing

user_config = os.path.expanduser("~") + '/.ldapsync.cfg'
parser = argparse.ArgumentParser(description='Invite LDAP-group users to MATRIX rooms (+ MATRIX groups if necessary) with:\n\n ./sync-users.py [yaml-spec-input] [json-policy-output]', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('yamlfile')
parser.add_argument('policyfile')
args = parser.parse_args()
yamlfile = args.yamlfile
policyfile = args.policyfile

# constants

## rooms that will not be controlled
IGNORED_ROOMS = [ 'testchannel' ]

## Matrix URL API constants
DOMAIN = 'domain.com'
MATRIX = 'https://matrix.' + DOMAIN + '/_matrix/client/r0'
ADMIN = 'https://matrix.' + DOMAIN + '/_synapse/admin/v1'

## LDAP server constants
LDAP_SERVER_IP = "10.10.10.10"
LDAP_SEARCH_BASE = 'dc=domain,dc=com'
## LDAP query to find users
LDAP_USER_QUERY = '(&(objectClass=person)(!(uid=appli*))(!(ou:dn:=disabled_accounts)))'

## LDAP and Matrix credentials from ini file
config = configparser.ConfigParser()
config.read(user_config)
MATRIX_ADMIN_ACCOUNT = config['matrix']['AdminUser']
MATRIX_ADMIN_PASSWORD = config['matrix']['AdminPassword']
TOKEN = config['matrix']['AdminToken']
AUTH = {'Authorization': 'Bearer ' + TOKEN}
LDAP_BIND_ACCOUNT = config['ldap']['BindAccount']
LDAP_BIND_PASSWORD = config['ldap']['BindPassword']

# functions

def spec_load_yaml(yamlfile):
    with open(yamlfile, 'r') as f:
        spec = yaml.load(f, Loader=yaml.FullLoader)
    return spec

def spec_groups(spec):
    return [ i.get('matrixgroup', []) for i in spec ]

def matrix_whoami():
    response = requests.get(MATRIX + '/account/whoami', headers=AUTH)
    print(response.json()['user_id'])

def matrix_compute_rooms_map():
    rooms = []
    response = requests.get(ADMIN + '/rooms', headers=AUTH)
    json = response.json()
    print(str(len(json['rooms'])) + " rooms found.")
    # compute rooms, a list of dicts of the form { 'name':"...", 'id':"..." }
    for r in json['rooms']:
        if r['name'] is not None:
            rooms.append({'name':r['name'], 'id':r['room_id']})
    print(str(len(rooms)) + " rooms with names found.")
    return rooms

def matrix_room_id(room_or_rooms, name = None):
    if type(room_or_rooms) == list:
        #print(f'matrix_room_id(len(rooms) = {len(room_or_rooms)}, name = {name})')
        if name in [ r['name'] for r in room_or_rooms]:
            return [r['id'] for r in room_or_rooms if r['name'] == name][0]
        else:
            # a non-existent id is requested: silently return nothing
            return None
    else:
        #print(f'matrix_room_id(room = {room_or_rooms}, name = {name})')
        return room_or_rooms['id']

def matrix_room_name(room_or_rooms, id = None):
    if type(room_or_rooms) == list:
        #print(f'matrix_room_name(len(rooms) = {len(room_or_rooms)}, id = {id})')
        if id in [ r['id'] for r in room_or_rooms ]:
            return [r['name'] for r in room_or_rooms if r['id'] == id][0]
        else:
            # a non-existent name is requested: silently return nothing
            return None
    else:
        #print(f'matrix_room_name(room = {room_or_rooms}, id = {id})')
        return room_or_rooms['name']

def ldap_init():
    ldap_server = Server(LDAP_SERVER_IP, port=636, use_ssl=True, get_info=ALL)
    return Connection(ldap_server, LDAP_BIND_ACCOUNT, LDAP_BIND_PASSWORD, auto_bind=True)

def ldap_get_usernames(querystring:str) -> list:
    ldap_conn.search(LDAP_SEARCH_BASE, querystring, attributes=["uid"])
    return [str(entry['uid'].values[0]).lower() for entry in ldap_conn.entries]

def ldap_get_dn_from_user(user):
    return "%s=%s,%s" % ("uid", user, "ou=users," + LDAP_SEARCH_BASE)

def ldap_get_dn_from_group(ldapgroup):
    if (ldapgroup.find('-') == -1):
        return '%s=%s,%s' % ("cn", ldapgroup, "ou=groups," + LDAP_SEARCH_BASE)
    else:
        return '%s=%s,%s' % ("cn", ldapgroup, "ou=packages,ou=groups," + LDAP_SEARCH_BASE)

def ldap_user_in_group(user, ldapgroup):
    group_search = ldap_get_dn_from_group(ldapgroup)
    group_object = '(objectclass=%s)' % "posixGroup"
    ldap_conn.search(group_search, group_object, attributes=['memberUid'])
    if len(ldap_conn.entries) < 1:
        return False
    members = ldap_conn.entries[0].memberUid.value
    return user in members

def ldap_group_members(ldapgroup):
    group_search = ldap_get_dn_from_group(ldapgroup)
    group_object = '(objectclass=posixGroup)'
    ldap_conn.search(group_search, group_object, attributes=['memberUid'])
    if len(ldap_conn.entries) < 1:
        return False
    members = ldap_conn.entries[0].memberUid.value
    if not isinstance(members, list):
        members = [ members ]
    return members

def policy_update_schema(version):
    POLICY.update( { "schemaVersion": version } )

def policy_update_flags(change_name = True, change_avatar = True, forbid_create_room = False):
    flags_data = {}
    flags_data['flags'] = {}
    flags_data['flags']['allowCustomUserDisplayNames'] = change_name
    flags_data['flags']['allowCustomUserAvatars'] = change_avatar
    flags_data['flags']['forbidRoomCreation'] = forbid_create_room
    flags_data['flags']['allowCustomPassthroughUserPasswords'] = False
    flags_data['flags']['forbidEncryptedRoomCreation'] = False
    flags_data['flags']['forbidUnencryptedRoomCreation'] = False

    POLICY.update(flags_data)

def policy_update_groups(list_of_groups):
    POLICY.update( { "managedCommunityIds": list_of_groups } )

def policy_update_rooms(list_of_rooms):
    POLICY.update( { "managedRoomIds": list_of_rooms } )

def policy_update_users(list_of_users):
    POLICY.update( { "users": list_of_users } )

# main

## initial policy
POLICY = {}

## check admin user
print ('Checking Matrix user...', end='')
matrix_whoami()

## parse YAML spec file
print ('Loading YAML specifications...', end='')
spec = spec_load_yaml(yamlfile)
print('Done.')
print('')
GROUPS = spec_groups(spec)

print("=== Will generate policy for the following Matrix groups: ===")
print(GROUPS)
print('')

## add schemaVersion
policy_update_schema(1)

## add flags
policy_update_flags()

## add managedCommunityIds
policy_update_groups(GROUPS)

## GET the list of all rooms with a name
print('Computing rooms map...', end='')
rooms = matrix_compute_rooms_map()

## filter the ones that are not under control of corporal
ROOMS = [ r for r in rooms if matrix_room_name(r) not in IGNORED_ROOMS ]
print(str(len(ROOMS)) + " rooms found that are controlled.")
print('')
print("=== Will generate policy for the following Matrix rooms: ===")
names = list(map(lambda room:matrix_room_name(room), ROOMS))
print(', '.join(names))
print('')

## add managedRoomIds
ROOMS_IDS = [ matrix_room_id(r) for r in ROOMS ]
policy_update_rooms(ROOMS_IDS)

## compute RESTRICTED room list from spec for all matrixgroups
## (i.e., rooms from each matrixgroup for which not all matrixgroup members have access)
RESTRICTED = []
for r in [ s['restricted'] for s in spec if 'restricted' in s ]:
    RESTRICTED += r
RESTRICTEDUSERS = []
RESTRICTEDGROUPS = []
for room in RESTRICTED:
    RESTRICTEDUSERS += room.get('users', [])
    RESTRICTEDGROUPS += room.get('groups', [])
RESTRICTEDUSERS = sorted(set(RESTRICTEDUSERS))
RESTRICTEDGROUPS = sorted(set(RESTRICTEDGROUPS))

## compute total LDAPGROUPS list from spec (starting with the restricted ones)
print('Computing LDAP groups...', end='')
LDAPGROUPS = RESTRICTEDGROUPS
for g in [ s['ldapgroups'] for s in spec if 'ldapgroups' in s ]:
    LDAPGROUPS += g
LDAPGROUPS = sorted(set(LDAPGROUPS))
print('Done.')
print('')
print("=== LDAP groups that are specified in the rooms ===")
print(LDAPGROUPS)
print('')

## compute total LDAPUSERS list from spec (starting with the restricted ones)
print('Computing LDAP users...', end='')
LDAPUSERS = RESTRICTEDUSERS
for u in [ s['ldapusers'] for s in spec if 'ldapusers' in s ]:
    LDAPUSERS += u
LDAPUSERS = sorted(set(LDAPUSERS))
print('Done.')
print('')
print("=== LDAP users that are specified in the rooms ===")
print(LDAPUSERS)
print('')

## init LDAP connection
print ('Connecting to LDAP server...', end='')
ldap_conn = ldap_init()
print('Done.')

## compute users of LDAP: list all users
print ('Computing users list...', end='')
active_users = ldap_get_usernames(LDAP_USER_QUERY)
print(str(len(active_users)) + " users found.")

## then for each LDAP group mentioned in the spec, compute LDAP users that are in required group
print ('Computing LDAP group users for each group...')
USERSINGROUP = {}
USERS = []
for group in LDAPGROUPS:
    print(" - LDAP group " + group + " = ", end='')
    USERSINGROUP[group] = [ u for u in ldap_group_members(group) if u in active_users ]
    print(f'{len(USERSINGROUP[group])} users')
    USERS += USERSINGROUP[group]

## add LDAPUSERS from spec that are directly mentionned
USERS += LDAPUSERS
USERS = sorted(set(USERS))
print('')
print(f'=== Will generate policy for {len(USERS)} Matrix users ===')
print("")

## compute all rooms IDs for each USERS and store it in USER_DATA: dict { <user> : dict {<groups>:[] <rooms>:[]} }
USER_DATA = {}
for user in USERS:
    USER_DATA[user] = {}
    USER_DATA[user]['matrix-groups'] = []
    USER_DATA[user]['matrix-rooms'] = []
    flag[user] ={}
    flag[user]['forbidroomcreation'] = {}
for i in spec:
    # get all data fields of a given matrixgroup
    matrixgroup = i.get('matrixgroup')
    matrixrooms = i.get('rooms', [])
    ldapusers = i.get('ldapusers', [])
    ldapgroups = i.get('ldapgroups', [])
    restrictedrooms = i.get('restricted', [])
    print(f'Matrix group {matrixgroup} includes rooms {matrixrooms}, LDAP groups {ldapgroups}...')
    # compute a global user list of all the groups
    for group in ldapgroups:
        ldapusers += USERSINGROUP[group]
    # for each user: add group+rooms membership to its data
    for user in ldapusers:
        if matrixgroup not in USER_DATA[user]['matrix-groups']:
            USER_DATA[user]['matrix-groups'].append(matrixgroup)
        rooms_names = list(map(lambda name:matrix_room_id(ROOMS,name), matrixrooms))
        USER_DATA[user]['matrix-rooms'] += [ i for i in rooms_names if i is not None ]
    # for each restricted room, for each of its user, add group+rooms membership
    for room in restrictedrooms:
        print(f'Restricted room: {room}...')
        restrictedusers = room.get('users', [])
        for restrictedgroup in room.get('groups', []):
            #print(f' + adding restricted users from {restrictedgroup}: ', end='')
            #print(USERSINGROUP[restrictedgroup])
            restrictedusers += USERSINGROUP[restrictedgroup]
        for user in restrictedusers:
            #print(f' + adding additional restricted users {user}:')
            if matrixgroup not in USER_DATA[user]['matrix-groups']:
                USER_DATA[user]['matrix-groups'].append(matrixgroup)
            id = matrix_room_id(ROOMS,room.get('room'))
            if id is not None and id not in USER_DATA[user]['matrix-rooms']:
                USER_DATA[user]['matrix-rooms'].append(id)
   ##read users that have the flag 'forbidroomcreation'
    forbidroomcreationgroups = i.get('ldapgroups-forbidroomcreation', [])
    forbidroomcreationusers = i.get('ldapusers-forbidroomcreation', [])
    print(f'forbidroomcreation {forbidroomcreationgroups}')
    for group in forbidroomcreationgroups:
       forbidroomcreationusers += USERSINGROUP[group]
    for user in forbidroomcreationusers:
        flag[user]['forbidroomcreation'] = 'true'
## For each user, add its policy section
list = []
for user in USERS:
    user_data = {}
    user_data['id'] = '@' + user + ':' + DOMAIN
    user_data['active'] = True
    user_data['authCredential'] = "http://matrix-ma1sd:8090/_matrix-internal/identity/v1/check_credentials"
    user_data['authType'] = "rest"
  #  user_data['joinedCommunityIds'] = USER_DATA[user]['matrix-groups'] #not working anymore due to spaces
    user_data['joinedRoomIds'] = USER_DATA[user]['matrix-rooms']
    if flag[user]['forbidroomcreation'] == 'true':
      user_data['forbidroomcreation'] = 'true'
    list.append(user_data)
policy_update_users(list)

## Print policy as JSON
print('')
print("========== Generating JSON ==========")
print('Done')
print('')
with open(policyfile, 'w') as outfile:
    json.dump(POLICY, outfile, indent=2, sort_keys=True)

exit()
