# Has interface for the database
#-----------------
# imports
import os
from sys import stderr, exit
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session, create_session, Session
from sqlalchemy.ext.automap import automap_base
#-------------------
# CAS Authentication cannot be run locally unfortunately
# Set this variable to 1 if local, and change to 0 before pushing
LOCAL_ENV = 0




#----------
DATABASE_URL = os.environ['DATABASE_URL']

# create engine (db object basically)
engine = create_engine(DATABASE_URL)
#start automap and create session with automap
Base = automap_base()
Base.prepare(engine, reflect=True)

session = Session(engine)

Users = Base.classes.users
Groups = Base.classes.groups
Group_members = Base.classes.groupmembers

# call this function on the preferences array
def create_preferences(hoursList):
    output = {}
    for i in range(len(hoursList)):
        output[i] = hoursList[i]
    return output

# dict to double array
# NOTE: Append recreates the array every time to add a new item to the end. Would be better to use a set sized array instead of expanding
# especially for big arrays
def get_double_array(preferences):
    output = []
    for i in range(len(preferences)):
        output.append(preferences[str(i)])
    return output






# adds a user to the database
def add_user(firstName, lastName, netid, email=None, phone=None, preferences=None):
    try:
        session.add(Users(firstname=firstName,lastname=lastName,netid=netid,email=email,phone=phone,globalpreferences=preferences))
        session.commit()
        return
    except:
        session.rollback()
        print('Add User Failed',file=stderr)
        return -1
        

def user_exists(netid):
    return session.query(Users).filter(Users.netid == netid).scalar() is not None
    
# removes a user from a group
def remove_user(netid, groupid):
    try:
        userid = get_user_id(groupid,netid)
        session.execute(
            "DELETE FROM groupmembers WHERE inc=:param", {"param":userid}
        )
        # session.delete(Group_members(inc=get_user_id(groupid,netid)))
        session.flush()
        session.commit()
    except:
        session.rollback()
        print('Remove User Failed',file=stderr)
        return -1
    return


#replaces the personal preferences of a user, global
def change_user_preferences_global(netid, preferences):
    try:
        session.add(Users(netid=netid, globalpreferences=preferences))
        session.commit()
    except:
        session.rollback()
        print('Failed to change users global preferences',file=stderr)
        return -1
    return

# this could break if we change database row names!
def get_global_preferences(netid):
    try:
        pref = session.query(Users.globalpreferences).filter_by(netid=netid).first()

        return pref._asdict()['globalpreferences']
        print(pref)
    except:
        print('get_global_preferences() failed',file=stderr)
        return -1

# get user's group preferences 
def get_group_preferences(groupid, netid):
    try:
        userid = get_user_id(groupid, netid)
        pref = session.query(Group_members.grouppreferences).filter_by(inc=userid).first()

        return pref._asdict()['grouppreferences']
    except:
        print('get_group_preferences() failed',file=stderr)
        return -1


# replaces weekly preferences of user. If none specified, 
# replaces it with global preferences
def change_user_preferences_group(groupid, netid, preferences = None):
    if(preferences==None):
       preferences = get_global_preferences(netid)
       # preferences = get_global_preferences(netid) ?
    

    userid = get_user_id(groupid,netid)
    if(userid == -1):
        return -1
    try:
        session.add(Group_members(inc=userid, grouppreferences = preferences))
        session.commit()
    except:
        session.rollback()
        print('Change_user_preferences_group() failed',file=stderr)
        return -1
    return

#used in above function to access primary key
#not intended for use in standalone function
def get_user_id(groupid,netid):
    try:
        userid = session.query(Group_members.inc).filter_by(groupid=groupid,netid=netid).first()
        # there's no inc key in users table? -> inc key is in groupmembers
        return userid
    except:
        print('get_user_id() failed',file=stderr)
        return -1

# Adds a group, shiftSchedule is optional argument if known
# should call add_user_to_group with owner role
def add_group(owner, groupName, shiftSchedule = None):
    statement = Groups(owner=owner, groupname=groupName,shiftSchedule=shiftSchedule)
    try:
        session.add(statement)
        session.flush()
        groupid=statement.groupid
        add_user_to_group(groupid,owner,'owner')
        session.commit()
    except:
        session.rollback()
        print('Failed to add_group()',file=stderr)
        return -1
        
    return



# removes a group
def remove_group(groupid):
    try:
        session.execute(
            "DELETE FROM groupmembers WHERE groupid=:param", {"param":groupid}
        )
        session.execute(
            "DELETE FROM groups WHERE groupid=:param", {"param":groupid}
        )
        # session.delete(Group_members(inc=get_user_id(groupid,netid)))
        session.flush()
        session.commit()
    except:
        session.rollback()
        print('Failed to remove group',file=stderr)
        return -1
    return


# Replaces the schedule of the group specified by groupid
def change_group_schedule(groupid, schedule):
    try:
        session.add(Groups(groupid=groupid, shiftSchedule=schedule))
        session.commit()
    except:
        session.rollback()
        print('change_group_schedule() failed',file=stderr)
        return -1
    return

# add a user (netid) to group (groupid), 
# preferences is optional argument, but could default to global if None???
# valid options for 'role' are: 'manager', 'owner', 'member'
def add_user_to_group(groupid, netid, role, email=False,text=False,preferences = None):
    try:
        session.add(Group_members(netid=netid,groupid=groupid,role=role,emailnotif=email,textnotif=text,grouppreferences=preferences))
        session.commit()
    except:
        session.rollback()
        print('Failed to add user to group',file=stderr)
        return -1
    return

# changes the role of a person (netid) in a group (groupid) to 'role'
def change_group_role(groupid, netid, role):
    userid=get_user_id(groupid,netid)
    if userid == -1:
        print('failed to change user role in group',file=stderr)
        return -1
    try:
        session.add(Group_members(inc=userid,role=role))
        session.commit()
    except:
        session.rollback()
        print('failed to change user role in group',file=stderr)
        return -1
    return

# change the notifications of a person in a group
# email and text should always be specified when calling this function
def change_group_notifications(groupid, netid, emailnotif = False, textnotif = False):
    userid = get_user_id(groupid,netid)
    if userid == -1:
        print('failed to change group notifications',file=stderr)
        return -1
    try:
        session.add(Group_members(inc=userid,emailnotif=emailnotif,textnotif=textnotif))
        session.commit()
    except:
        session.rollback()
        print('failed to change group notifications',file=stderr)
        return -1
    return

# retrieve name, email, phone from user table
def get_profile_info(netid):
    try:
        userInfo = session.query(Users.firstname, Users.lastname, Users.email, Users.phone).filter_by(netid=netid).first()
        return userInfo
    except:
        print('Failed to get profile info',file=stderr)
        return -1

# retrieve user's notification preferences from specific group
def get_group_notifications(netid, groupid):
    try:
        userid = get_user_id(groupid, netid)
        notifPrefs = session.query(Group_members.emailnotif, Group_members.textnotif).filter_by(inc=userid).first()
        return notifPrefs
    except:
        print('Failed to get group notifications',file=stderr)
        return -1

# updates profile info
# (name, email, phone)
def update_profile_info(firstName, lastName, netid, email=None, phone=None, preferences=None):
    try:
        session.query(Users).filter_by(netid=netid).update({Users.firstname : firstName, Users.lastname: lastName, Users.email: email, Users.phone: phone, Users.globalpreferences: preferences})
        session.commit()
    except:
        session.rollback()
        print('Failed to update user profile',file=stderr)
        return -1
    return

# get all groupids of groups that user is part of 
# (queries with netid instead of inc b/c each group that a user is in has different inc in groupmembers table)
# returns list of groupids
def get_user_groups(netid):
    try:
        groups = session.query(Group_members.groupid).filter_by(netid=netid).all()
        group_names = []
        for g in groups:
            group_names.append(session.query(Groups.groupname).filter_by(groupid=g.groupid).first())
        return group_names
    except:
        return -1

def rollback():
    session.rollback()
    return

if __name__=="__main__":
    # test
    # add_user('batya','stein','batyas',email='batyas@princeton.edu',phone='7327660532')
    #add_user_to_group(1, 'batyas','member')

    #update_profile_info('test', 'user', 'test123', email = 'test@test.com', preferences=create_preferences([[1,2],[1,2]]))
    #print(user_exists('test2'))
    #add_group('dlsnyder', 'Test Group 2')
    #add_user_to_group(3, 'test2', 'user')
    groups = get_user_groups('test2')
    '''
    print(len(groups))
    for g in groups:
       print(g.groupname)
    #remove_group(2)
    remove_user('test2',3)
    '''
    print(get_group_preferences(1,'test2'))