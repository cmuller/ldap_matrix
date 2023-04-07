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
import hmac
import hashlib
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
#IGNORED_ROOMS = [ 'testchannel' ]

## Matrix URL API constants
#ideally the policy is created on the matrixserver directly, so no security issue with shared-secret
DOMAIN = 'matrix.domain.com'
DOMAINURL = 'http://'+ DOMAIN
MATRIX = 'http://' + DOMAIN + ':8008/_matrix/client/r0'
ADMIN = 'http://' + DOMAIN + ':8008/_synapse/admin/v1'

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
#shared secret used instead of password
MATRIX_SHARED_SECRET = config['matrix']['SharedSecret']

LDAP_BIND_ACCOUNT = config['ldap']['BindAccount']
LDAP_BIND_PASSWORD = config['ldap']['BindPassword']

# functions

#this function was created by devture.sharedsecretauth
def obtain_access_token(full_user_id, homeserver_api_url, shared_secret):
    login_api_url = homeserver_api_url + ':8008/_matrix/client/r0/login'
    token = hmac.new(shared_secret.encode('utf-8'), full_user_id.encode('utf-8'), hashlib.sha512).hexdigest()
    payload = {
        'type': 'com.devture.shared_secret_auth',
        'identifier': {
          'type': 'm.id.user',
          'user': full_user_id,
        },
        'token': token,
    }
      #code for password login instead of shared secret
    # If `m_login_password_support_enabled`, you can use `m.login.password`.
    # The token goes into the `password` field for this login type, not the `token` field.
    #
    # payload = {
    #     'type': 'm.login.password',
    #     'identifier': {
    #       'type': 'm.id.user',
    #       'user': full_user_id,
    #     },
    #     'password': token,
    # }
    response = requests.post(login_api_url, data=json.dumps(payload))
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def create_space(roomname, AUTH):
       #AUTH=obtain_access_token('@'+ roomcreator +':'+ DOMAIN, DOMAINURL, MATRIX_SHARED_SECRET)
       url=DOMAINURL+':8008/_matrix/client/r0/createRoom'
       payload = {
              'room_alias_name': roomname,
              'creation_content': {
                  'type': 'm.space',
                  },
              'name': roomname,
              'preset':'private_chat',
       }
       response=requests.post(url, data=json.dumps(payload), headers=AUTH)
       if str(response) == '<Response [200]>':
           print("Space:"+ roomname +"has been successfully created")
       return None

def create_room(roomname, AUTH):
       #AUTH=obtain_access_token('@'+ roomcreator +':'+ DOMAIN, DOMAINURL, MATRIX_SHARED_SECRET)
       url=DOMAINURL+':8008/_matrix/client/r0/createRoom'
       payload = {
                  'room_alias_name': roomname,
                  'name': roomname,
                  'preset':'private_chat',
       }
       #print(payload)
       response=requests.post(url, data=json.dumps(payload), headers=AUTH)
       if str(response) == '<Response [200]>':
           print("Room"+ roomname +"has been successfully created")
       return None

def move_room(roomname, parentroom, roommap,AUTH):
      # method=PUT uri="/_matrix/client/r0/rooms/!UjQqBRgxQUFzvwbjsf:matrix.wgs-albstadt.de/state/m.space.child/!QQMfqytsqBvNzexoUW:matrix.wgs-albstadt.de"

     # url=DOMAINURL+':8008/_matrix/client/r0/rooms/'+ o /
     # payload={ 
       print(" ")
       id_roomname= id_room(roomname,roommap)
       id_parentroom = id_room(parentroom,roommap)
      # print(id_parentroom)
      # print(id_roomname)
       url=DOMAINURL+':8008/_matrix/client/r0/rooms/'+ id_parentroom + '/state/m.space.child/'+ id_roomname
       payload={
                  'via': [DOMAIN],
              }
       #print(list(roommap))
       #list(roommap).index({'name': roomname})     




       #print(json.dumps(payload))
       response=requests.put(url,data=json.dumps(payload), headers=AUTH)
       return None


def id_room(roomname,roommap):
    return [room for room in roommap if room['name']== roomname][0]['id']


def spec_load_yaml(yamlfile):
    with open(yamlfile, 'r') as f:
        spec = list(yaml.load_all(f, Loader=yaml.FullLoader))
    return spec[1]

def spec_load_yaml_flags(yamlfile):
    with open(yamlfile, 'r') as f:
        spec = list(yaml.load_all(f, Loader=yaml.FullLoader))
    return spec[0]


def spec_rooms(spec):
    return [ i.get('room', i.get('space',[])) for i in spec ]

def matrix_whoami():
    response = requests.get(MATRIX + '/account/whoami', headers=ADMINAUTH)
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
#define global flag settings
def policy_update_flags():
    flags_data = {}
    flags_data['flags'] = {}
    flags_data['flags']['allowCustomUserDisplayNames'] = False
    flags_data['flags']['allowCustomUserAvatars'] = False
    flags_data['flags']['forbidRoomCreation'] = False
    flags_data['flags']['allowCustomPassthroughUserPasswords'] = False
    flags_data['flags']['forbidEncryptedRoomCreation'] = False
    flags_data['flags']['forbidUnencryptedRoomCreation'] = False
    POLICY.update(flags_data)


def policy_update_rooms(list_of_rooms):
    POLICY.update( { "managedRoomIds": list_of_rooms } )

def policy_update_users(list_of_users):
    POLICY.update( { "users": list_of_users } )

# main

## initial policy
POLICY = {}

ADMINAUTH = obtain_access_token(MATRIX_ADMIN_ACCOUNT, DOMAINURL, MATRIX_SHARED_SECRET)

## check admin user
print ('Checking Matrix user...', end='')
matrix_whoami()

## parse YAML spec file
print ('Loading YAML specifications...', end='')
spec = spec_load_yaml(yamlfile)
spec_flags = spec_load_yaml_flags(yamlfile)
print('Done.')
print('')
spec_rooms = spec_rooms(spec)

## add schemaVersion
policy_update_schema(1)

## add flags
policy_update_flags()

## add managedCommunityIds
policy_update_groups(GROUPS)

## GET the list of all existing rooms in matrix with a name
print('Computing rooms map...', end='')
existingrooms = matrix_compute_rooms_map()
#print(existingrooms)
## filter the ones that are not under control of corporal
## filter the ones that are listed in yaml but not in matrix
    # compute rooms, a list of dicts of the form { 'name':"...", 'id':"..." }

ROOMStobecreated = [ r for r in spec_rooms if r not in [i.get('name') for i in existingrooms] ]
print(' ')

print(str(len(ROOMStobecreated)) + " rooms found in yaml that do not exist in Matrix yet.")

if len(ROOMStobecreated) > 0:
   print("=== Going to create the following rooms:"+ str(ROOMStobecreated))
   print('')

   for i in spec:
        if i.get('space',[]) in [r for r in ROOMStobecreated]:
           create_space(i.get('space',[]), ADMINAUTH)
        if i.get('room',[]) in [r for r in ROOMStobecreated]:
           create_room(i.get('room',[]),ADMINAUTH)
    #theoretically the code could be easily changed in a way that the rooms could be directly created by a designated person that becomes then roomadmin of the room,
    #however, matrix-corporal relies on the fact that a single admin accoount is enrolled in all the managed rooms    

   print('Recomputing rooms map...', end='')
   existingrooms = matrix_compute_rooms_map()
  # print(existingrooms)

   print('===Move Rooms to their parent room/space...', end='')
   print(' ')
   for i in spec:
       if i.get('room',[]) in [r for r in ROOMStobecreated]:
           if i.get('childof',None) is not None:
              move_room(i.get('room',[]),i.get('childof',[]),existingrooms,ADMINAUTH)




## add managedRoomIds
ROOMS=[r for r in  existingrooms if r.get('name') in spec_rooms]
print(spec_rooms)
ROOMS_IDS = [ matrix_room_id(rs) for rs in ROOMS ]
policy_update_rooms(ROOMS_IDS)



### compute total LDAPGROUPS list from spec (starting with the restricted ones)
print('Computing LDAP groups...', end='')
LDAPGROUPS=[]
for i in spec:
    LDAPGROUPS += i.get('ldapgroups',[])
for g in [spec_flags.get('ldapgroups-forbidroomcreation',[])]:
    LDAPGROUPS += g
for g in [spec_flags.get('ldapgroups-forbidencryptedroomcreation',[])]:
    LDAPGROUPS += g
for g in [spec_flags.get('ldapgroups-forbidunencryptedroomcreation',[])]:
    LDAPGROUPS += g
LDAPGROUPS = sorted(set(LDAPGROUPS))
print('Done.')
print('')
print("=== LDAP groups that are specified in any rooms or spaces ===")
print(LDAPGROUPS)
print('')

## compute total LDAPUSERS list from spec 
print('Computing LDAP users...', end='')
LDAPUSERS = []
for u in [ s['ldapusers'] for s in spec if 'ldapusers' in s ]:
   LDAPUSERS += u
LDAPUSERS = sorted(set(LDAPUSERS))
print('Done.')
print('')
print("=== LDAP users that are specified in the rooms ===")
#print(LDAPUSERS)
print('')


## init LDAP connection
print ('Connecting to LDAP server...', end='')
ldap_conn = ldap_init()
print('Done.')

## compute users of LDAP: list all users
print ('Computing users list...', end='')
active_users = ldap_get_usernames(LDAP_USER_QUERY)
#inactive_users= ldap_get_usernames('(&(objectclass=inetorgperson)(|(|(logindisabled=true)(ou=Rossental))(initials=noLehrer)))')
print(str(len(active_users)) + " users found.")
#print(active_users) 
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
#print(f'=== Will generate policy for {len(USERS)} Matrix users ===')
print("")

## compute all rooms IDs for each USERS and store it in USER_DATA: dict { <user> : dict {<groups>:[] <rooms>:[]} }
USER_DATA = {}
for user in USERS:
    USER_DATA[user] = {}
   # USER_DATA[user]['matrix-groups'] = []
    USER_DATA[user]['matrix-rooms'] = []
    USER_DATA[user]['displayName'] = {}
    USER_DATA[user]['forbidroomcreation'] = False
    USER_DATA[user]['forbidencryptedroomcreation'] = False
    USER_DATA[user]['forbidunencryptedroomcreation'] = False

for i in spec:
  #  # get all data fields of a given matrixgroup
 #   matrixgroup = i.get('matrixgroup')
     ROOM = i.get('room', i.get('space',[]))
     ldapusers = i.get('ldapusers', [])
     ldapgroups = i.get('ldapgroups', [])
   # restrictedrooms = i.get('restricted', [])
     print(f'Room {ROOM} includes LDAP groups {ldapgroups}...')
    # compute a global user list of all the groups
     for group in ldapgroups:
       ldapusers += USERSINGROUP[group]
    # for each user: add group+rooms membership to its data
     for user in ldapusers:
           # if matrixgroup not in USER_DATA[user]['matrix-groups']:
           #     USER_DATA[user]['matrix-groups'].append(matrixgroup)
          id = matrix_room_id(existingrooms, ROOM)
          if id is not None and id not in USER_DATA[user]['matrix-rooms']:
                USER_DATA[user]['matrix-rooms'].append(id)


#old restricted group code
   #     if matrixgroup not in USER_DATA[user]['matrix-groups']:
    #        USER_DATA[user]['matrix-groups'].append(matrixgroup)
     #   rooms_names = list(map(lambda name:matrix_room_id(ROOMS,name), matrixrooms))
      #  USER_DATA[user]['matrix-rooms'] += [ i for i in rooms_names if i is not None ]
    # for each restricted room, for each of its user, add group+rooms membership
  #  for room in restrictedrooms:
   #     print(f'Restricted room: {room}...')
    #    restrictedusers = room.get('users', [])
     #   for restrictedgroup in room.get('groups', []):
        #    restrictedusers += USERSINGROUP[restrictedgroup]
       # for user in restrictedusers:
            #print(f' + adding additional restricted users {user}:')
           # if matrixgroup not in USER_DATA[user]['matrix-groups']:
           #     USER_DATA[user]['matrix-groups'].append(matrixgroup)
           # id = matrix_room_id(ROOMS,room.get('room'))
           # if id is not None and id not in USER_DATA[user]['matrix-rooms']:
           #     USER_DATA[user]['matrix-rooms'].append(id)

#set flags for users        
forbidroomcreationusers=[]
forbidencryptedroomcreationusers=[]
forbidunencryptedroomcreationusers=[]

for group in spec_flags.get('ldapgroups-forbidroomcreation',[]):
    forbidroomcreationusers += USERSINGROUP[group]
for user in forbidroomcreationusers:
    USER_DATA[user]['forbidroomcreation'] = True
for group in spec_flags.get('ldapgroups-forbidencryptedroomcreation',[]):
    forbidencryptedroomcreationusers += USERSINGROUP[group]
for user in forbidencryptedroomcreationusers:
    USER_DATA[user]['forbidencryptedroomcreation'] = True
for group in spec_flags.get('ldapgroups-forbidunencryptedroomcreation',[]):
    forbidunencryptedroomcreationusers += USERSINGROUP[group]
for user in forbidunencryptedroomcreationusers:
    USER_DATA[user]['forbidunencryptedroomcreation'] = True
                
                
                
                
## For each user, add its policy section
list = []
for user in USERS:
    user_data = {}
    user_data['id'] = '@' + user + ':' + DOMAIN
    user_data['active'] = True
    user_data['authCredential'] = "http://matrix-ma1sd:8090/_matrix-internal/identity/v1/check_credentials"
    user_data['authType'] = "rest"
    user_data['joinedCommunityIds'] = USER_DATA[user]['matrix-groups']
    user_data['joinedRoomIds'] = USER_DATA[user]['matrix-rooms']
    user_data['forbidRoomCreation'] = USER_DATA[user]['forbidroomcreation']
    user_data['forbidUnencryptedRoomCreation'] = USER_DATA[user]['forbidunencryptedroomcreation']
    user_data['forbidEncryptedRoomCreation'] = USER_DATA[user]['forbidencryptedroomcreation']
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
