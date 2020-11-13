from flask import Flask
from flask import render_template, make_response, request, redirect, url_for
from CASClient import CASClient
from flask_mail import Mail, Message

from database import *
from shifttest import *

import os
import json
from sys import stderr, exit
import urllib.parse as urlparse

#-------------------
# CAS Authentication cannot be run locally unfortunately
# Set this variable to False if local, and change to True before pushing
PROD_ENV = True


#----------


app = Flask(__name__)
app.secret_key = b'\x06)\x8e\xa3BW"\x9d\xcd\x1d5)\xd6\xd1b1'
app.config.update(dict(
    DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = os.environ['MAIL_USERNAME'],
    MAIL_PASSWORD = os.environ['MAIL_PW'],
))
mail = Mail(app)


def filter_shifts(netid,shifts):
    newdict = dict()
    for (key, value) in shifts.items():
        print(key,value)
        for name in value:
            print("name:",name)
            if name == netid:
                newdict[key] = name
    print("dict:\n",newdict)
    return newdict

# This function will email every member in a group with their schedule for the next week.
# It will assume that the schedule in groupmembers.userschedule is the one to use
def email_group(groupid, groupName):
    members = get_group_users(groupid) # get all group members
    shifts = get_group_schedule(groupid) # group schedule
    if not shifts:
        shifts = {}
    
    with mail.connect() as conn:
        for netid in members:
            mem_info = get_profile_info(netid) # get profile info
            sched = filter_shifts(netid,shifts) # get their weekly schedule
            # sched = shifts_to_us_time(shift)
            
            output = formatDisplaySched(sched)
            
            html = "<strong>This week's shifts are:</strong><br>"
            
            for (key, value) in output.items():
                print(key)
                html += key + "<br>"
            # html = "<strong>This week's shifts are:</strong><br>"
            #for i in sched:
            #   html += '<strong>Day: </strong>' + shifts[i][0] + '<strong>Start: </strong>' + \
            #          shifts[i][1] + '<strong>End: </strong>' + shifts[i][2] + '<br>'
            subject = "Your weekly schedule for: %s" % groupName
            
            # print("html: \n",html)
            

            msg = Message(subject=subject, 
                          html=html,   
                          recipients=[mem_info.email],
                          sender='sdylan852@gmail.com')
                        
            conn.send(msg)
    print("Group %s has been emailed" %groupName)
    return





# obtains username
def get_username():
    if PROD_ENV:
        username = CASClient().authenticate()
        username = username.rstrip('\n')
        return username

    else:
        return 'batyas'


# if user in group, gets groupname and id stored in cookie
# if nothing stored, defaults to first group in list of user's groups
def getCurrGroupnameAndId(request, groups, inGroup=True):
    groupname = request.cookies.get('groupname')
    if groupname == None and inGroup:
        groupname = groups[0][1]

    groupid = request.cookies.get('groupid')
    if groupid == None and inGroup:
        groupid = groups[0][0]
    elif inGroup: groupid = int(groupid)
    return groupname, groupid


# returns bool - is user owner or manager
# (used to display manage group tab in navbar if relevant)
def getIsMgr(username, inGroup, request, groups=None):
    if inGroup:
        if groups == None:
            groups = get_user_groups(username)
        _, groupid = getCurrGroupnameAndId(request, groups)
        role = get_user_role(username, groupid)
        if role == -1:
            return role
        return (role in ['manager','owner'])
    else:
        return False


# returns bool if owner
def getIsOwner(username, inGroup, groupid=None, request=None, groups=None):
    if not inGroup: 
        return False
    if inGroup and groupid==None:
        if groups == None:
            groups = get_user_groups(username)
        _, groupid = getCurrGroupnameAndId(request, groups)
    role = get_user_role(username, groupid)
    return role == "owner"

# takes a request and returns the schedule values
def parseSchedule():
    table_values = []
    slot_num = 24  # number of time slots in schedule, should be even
    for i in range(slot_num):  # iterates through time slots
        time = i
        week = []
        for day in range(7):  # iterates through days in a week
            if i < (slot_num/2):
                split = "0"
            else:
                split = "1"
            hour = time % 12
            if hour == 0:
                hour = 12
            str_call = str(hour) + "-" + str(1+((time) % 12)) + "-" + str(split) + "-" + str(day)
            week.append(request.form.get(str_call))
        table_values.append(week)

    for i in range(len(table_values)):
        for j in range(len(table_values[i])):
            if table_values[i][j] is None:
                table_values[i][j] = False
            else:
                table_values[i][j] = True

    return table_values


# creates a test schedule
def testSchedule():
    table_values = []
    slot_num = 24  # number of time slots in schedule, should be even
    for i in range(slot_num):  # iterates through time slots
        week = []
        for day in range(7):  # iterates through days in a week
            if day % 2 == 0:
                week.append(True)
            else:
                week.append(False)
        table_values.append(week)
    return table_values


# creates a blank schedule
def blankSchedule():
    table_values = []
    slot_num = 24  # number of time slots in schedule, should be even
    for i in range(slot_num):  # iterates through time slots
        week = []
        for day in range(7):  # iterates through days in a week
            week.append(False)
        table_values.append(week)
    return table_values

def military_to_us_time(time):
    if int(time.split(':')[0]) == 0:
        time = "12:00 AM"
    elif int(time.split(':')[0]) < 12:
        time = str(int(time.split(":")[0])) + ":00 AM"
    elif int(time.split(':')[0]) > 12:
        time = str(int(time.split(":")[0]) - 12) + ":00 PM"
    return time

def shiftdict_to_us_time(shifts):
    for i in shifts:
        shifts[i][1] = military_to_us_time(shifts[i][1])
        shifts[i][2] = military_to_us_time(shifts[i][2])
    return shifts

def shiftkey_to_str(shiftkey, full=False):
    days_to_nums = {'Sunday': 0, 'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6}
    nums_to_days = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    split = shiftkey.split('_')
    shiftString = "{} {} - {}".format(nums_to_days[int(split[0])],military_to_us_time(split[1]), military_to_us_time(split[2]))
    return shiftString

def formatDisplaySched(currsched):
    if currsched: 
        keys = sorted(currsched.keys())
        schedStrings = {}
        for key in keys:
            schedStrings[shiftkey_to_str(key)] = currsched[key]
        currsched = schedStrings
    else: currsched = {}
    return currsched


# returns list of elements in new but not old, and users in old but not new
def getDifferences(newlist, oldlist):
    newElements = []
    lostElements = []
    for element in newlist:
        if element not in oldlist:
            newElements.append(element)
            print("new element " + element)
    for element in oldlist:
        if element not in newlist:
            lostElements.append(element)
            print("removed element " + element)
    return newElements, lostElements


#------------------------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET','POST'])
def index():
    username = get_username()
    
    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    groups = get_user_groups(username)
    numGroups = len(groups)
    inGroup = (numGroups != 0)
    isMgr = getIsMgr(username, inGroup, request, groups)
    if isMgr == -1: groupname = groupid = None
    else: groupname, groupid = getCurrGroupnameAndId(request, groups, inGroup)
    isOwner = getIsOwner(username, inGroup, request=request, groups=groups)
    groups_by_name = [g[1] for g in groups]

    teststring = "user = " + username
    if isMgr: teststring += "is manager "
    else: teststring += "is not manager "
    #teststring += "of group " + groupname
    print(teststring)


    if request.method == 'GET':
        html = render_template('index.html', groups=groups_by_name, groupname=groupname, numGroups=numGroups, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner)
        response = make_response(html)
        return response

    else:
        groupname = request.form['groupname']
        groupid = get_group_id(groupname)
        isMgr = (get_user_role(username, groupid) in ["manager", "owner"])
        isOwner = (get_user_role(username, groupid) == 'owner')

        html = render_template('index.html',groups=groups_by_name, groupname=groupname, numGroups=numGroups, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner)
        response = make_response(html)
        response.set_cookie('groupname', groupname)
        response.set_cookie('groupid', str(groupid))
        return response


@app.route('/owner', methods=['GET', 'POST'])
def owner():
    username = get_username()
    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    groups = get_user_groups(username)
    inGroup = (len(groups) != 0)
    groupname, groupid = getCurrGroupnameAndId(request, groups, inGroup)

    users = get_group_users(groupid)
    users.remove(username)
    managers = []
    roles = {}
    isManager = {}
    for user in users:
        role = get_user_role(user, groupid)
        roles[user] = role
        if role == "manager":
            isManager[user] = True
            managers.append(user)
        else:
            isManager[user] = False

    if request.method == "GET":
        html = render_template('owner.html', inGroup=inGroup, users=users, isManager=isManager, groupname=groupname, isMgr=True, isOwner=True)
        response = make_response(html)
        return response
    else:
        selectedManagers = []
        for user in users:
            if request.form.get(user) is not None:
                selectedManagers.append(user)

        newManagers, removedManagers = getDifferences(selectedManagers, managers)

        for user in newManagers:
            change_group_role(groupid, user, 'manager')
            isManager[user] = True
        for user in removedManagers:
            change_group_role(groupid, user, 'member')
            isManager[user] = False

        html = render_template('owner.html', inGroup=inGroup, users=users, isManager=isManager, groupname=groupname, isMgr=True, isOwner=True)
        response = make_response(html)
        return response


@app.route('/profile', methods=['GET'])
def profile():
    username = get_username()

    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    userInfo = get_profile_info(username)
    inGroup = in_group(username)
    isMgr = getIsMgr(username, inGroup, request)
    isOwner = getIsOwner(username, inGroup, request=request)

    globalPreferences = blankSchedule()
    try:
        globalPreferences = get_double_array(get_global_preferences(username))
    except Exception:
        pass

    html = render_template('profile.html', firstName=userInfo.firstname, lastName=userInfo.lastname, netid=username, email=userInfo.email, 
        schedule=globalPreferences, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner, editable=False)

    response = make_response(html)

    return response

@app.route('/manage', methods=['GET','POST'])
def manage():
    username = get_username()

    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    groups = get_user_groups(username)

    if len(groups) == 0:
        return redirect(url_for('index'))

    isMgr = getIsMgr(username, True, request, groups)
    if not isMgr:
        return redirect(url_for('index'))

    users = get_all_users()
    users.remove(username)
    groupname, groupid = getCurrGroupnameAndId(request, groups, True)

    curr_members = get_group_users(groupid)
    isOwner = getIsOwner(username, True, groupid)
    selected = {}
    mgrs = {}

    for user in users:
        selected[user] = False
        if user in curr_members: 
            user_role = get_user_role(user, groupid)
        else:
            user_role = "notGroup"
        mgrs[user] = (user_role, (user_role in ['owner','manager']))
    for member in curr_members:
        selected[member] = True

    print(selected)
    shifts = get_group_shifts(groupid)
    if not shifts:
        shifts = {}
    
    currsched = get_group_schedule(groupid)
    currsched = formatDisplaySched(currsched)
    
    if request.method == 'GET':
        shifts = shiftdict_to_us_time(shifts)
        html = render_template('manage.html', groupname=groupname, inGroup=True, isMgr=isMgr, shifts=shifts, users=users, mgrs=mgrs, selected=selected, currsched=currsched, username=username, isOwner=isOwner)
        response = make_response(html)
        return response

    else:
        schednotif = False
        groupid = get_group_id(groupname)

        if request.form["submit"] == "Add":
            days_to_nums = {'Sunday': 0, 'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6}

            day = request.form["day"]
            start = request.form["start"]
            end = request.form["end"]
            npeople = request.form["npeople"]
            
            shift = [day, start, end, npeople]
            shiftid = "{}_{}_{}".format(days_to_nums[day],start.split(":")[0],end.split(":")[0])
            shifts[shiftid]=shift
        
            # change double array of shifts to dict, update db
            change_group_shifts(groupid, shifts)
        elif request.form["submit"] == "Save":
            n_user_list = []
            curr_members.remove(username)
            for user in users:  # adds users
                if request.form.get(user) is not None:
                    exists = False
                    n_user_list.append(user)
                    for member in curr_members:
                        if user == member:
                            exists = True
                    if not exists:
                        add_user_to_group(groupid, user, 'member')
                        print("added user" + user)
            for member in curr_members:  # removes users
                remains = False
                for user in n_user_list:
                    if member == user:
                        remains = True
                        print("user remains" + user)
                if not remains:
                    remove_user_from_group(member, groupid)
                    print("removed" + member)

            selected = {}
            for user in users:
                selected[user] = False
            for n_user in n_user_list:
                selected[n_user] = True
        elif request.form["submit"] == "Delete":
            remove_group(groupid)
            groups = get_user_groups(username)
            inGroup = (len(groups) > 0)
            if inGroup:
                groupid = groups[0][0]
                groupname = groups[0][1]
            response = make_response(redirect(url_for("index")))
            response.set_cookie('groupname', groupname)
            response.set_cookie('groupid', str(groupid))
            return response
        elif request.form["submit"] == "Generate Schedule":
            try:
                currsched = generate_schedule(groupid)
            except:
                currsched = None
            if (currsched == {}):
                currsched = None

            if currsched is not None:
                change_group_schedule(groupid, currsched)
                currsched = formatDisplaySched(currsched)
                # reset weekly group prefs of all group members
                groupmems = get_group_members(groupid)
                for mem in groupmems:
                    change_user_preferences_group(groupid, mem)
                schednotif = True
        else:
            shiftid = request.form["submit"]
            del shifts[shiftid]
            change_group_shifts(groupid, shifts)
        shifts = shiftdict_to_us_time(shifts)
        html = render_template('manage.html', groupname=groupname, inGroup=True, isMgr=isMgr, shifts=shifts, users=users, mgrs=mgrs, selected=selected, currsched=currsched, schednotif=schednotif, isOwner=isOwner, username=username)
        response = make_response(html)
        return response

@app.route('/schedule', methods=['GET'])
def schedule():
    username = get_username()
    
    if not (user_exists(username)):
        return redirect(url_for('createProfile'))
    
    groups = get_user_groups(username)

    if len(groups) == 0:
        return redirect(url_for('index'))

    groupname, groupid = getCurrGroupnameAndId(request, groups)
    isMgr = getIsMgr(username, True, request, groups)
    isOwner = getIsOwner(username, True, groupid)
    
    groupsched = get_group_schedule(groupid)
    if groupsched is not None:
        schedule = get_double_array(parse_user_schedule(username, groupsched))
    else:
        schedule = groupsched
    
    shifts = get_group_shifts(groupid)
    if not shifts:
        shifts = {}
    else:
        shifts = shiftdict_to_us_time(shifts)
       

    html = render_template('schedule.html', schedule=schedule , groupname=groupname, inGroup=True, isMgr=isMgr, editable=False,
        shifts=shifts, isOwner=isOwner)
    response = make_response(html)

    return response

@app.route('/group', methods=['GET'])
def group():
    username = get_username()

    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    groups = get_user_groups(username)

    if len(groups) == 0:
        return redirect(url_for('index'))

    groupname, groupid = getCurrGroupnameAndId(request, groups)
    isMgr = getIsMgr(username, True, request, groups)
    isOwner = getIsOwner(username, True, groupid)
    groupprefs = get_group_preferences(groupid, username)
    print(groupprefs)
    if groupprefs == None:
        change_user_preferences_global(username, create_preferences(blankSchedule()))
        groupprefs = get_global_preferences(username)
    weeklyPref = get_double_array(groupprefs)
        
    # later add code to reset groupprefs to global prefs on sunday

    notifPrefs = get_group_notifications(username, groupid)
    if notifPrefs != None and notifPrefs != -1: 
        prevemailPref = notifPrefs.emailnotif
    else:
        prevemailPref = False

    html = render_template('group.html', schedule=weeklyPref, groupname=groupname, prevemailPref=prevemailPref, 
        inGroup=True, isMgr=isMgr, isOwner=isOwner, editable=False)
    response = make_response(html)
    return response

@app.route('/editGroup',methods=['GET', 'POST'])
def editGroup():
    username = get_username()

    if not (user_exists(username)):
        return redirect(url_for('createProfile'))

    groups = get_user_groups(username)

    if len(groups) == 0:
        return redirect(url_for('index'))

    groupname, groupid = getCurrGroupnameAndId(request, groups)
    isMgr = getIsMgr(username, True, request, groups)
    isOwner = getIsOwner(username, True, groupid)

    groupprefs = get_group_preferences(groupid, username)
    if groupprefs == None:
        change_user_preferences_global(username, create_preferences(blankSchedule()))
        groupprefs = get_global_preferences(username)
    weeklyPref = get_double_array(groupprefs)
        
    # later add code to reset groupprefs to global prefs on sunday

    prevemailPref = get_group_notifications(username, groupid).emailnotif

    if request.method == 'GET':
        html = render_template('editGroup.html', schedule=weeklyPref, groupname=groupname, prevemailPref=prevemailPref,  
            inGroup=True, isMgr=isMgr, isOwner=isOwner, editable=True)
        response = make_response(html)
        return response
    else:
        prefemail = request.form.get('prefemail')
        if prefemail == 'on': 
            prefemail = True
        else:
            prefemail = False
        change_group_notifications(groupid, username, prefemail)

        prefs = create_preferences(parseSchedule())
        change_user_preferences_group(groupid, username, prefs)
        
        return redirect(url_for('group'))


@app.route('/populateUsers', methods=['GET'])
def populateUsers():
    add_user('John', 'Doe', 'jdoe')
    add_user('Jane', 'Doe', 'jadoe')
    add_user('Bland', 'Land', 'bland')
    add_user('Dan', 'Man', 'dman')
    add_user('Tom', 'Till', 'ttill')
    add_user('Jen', 'Jill', 'jjill')
    print("Populated Users")
    return redirect(url_for('index'))

@app.route('/cleanGroups', methods=['GET'])
def cleanGroups():
    username = get_username()

    groups = get_user_groups(username)
    if len(groups) == 0:
        return redirect(url_for('index'))
    # groups is list of tuples - (groupid, groupname), so create list of groupids from group list
    groupIds = [g[0] for g in groups]
    for groupId in groupIds:
        remove_group(groupId)
    print("DELETED ALL GROUPS")
    return redirect(url_for('index'))

@app.route('/viewGroup', methods=['GET'])
def viewGroup():
    username = get_username()
    inGroup = in_group(username)
    if not inGroup:
        return redirect(url_for('index'))
    groups = get_user_groups(username)
    isMgr = getIsMgr(username, True, request, groups)
    gName, groupId = getCurrGroupnameAndId(request, groups)
    isOwner = getIsOwner(username, True, groupId)

    members = get_group_users(groupId)
    members_w_roles = [(member, get_user_role(member, groupId)) for member in members]        
    html = render_template('viewGroup.html', gName=gName, members=members_w_roles, inGroup=True, isMgr=isMgr, isOwner=isOwner)
    response = make_response(html)

    return response


@app.route('/createGroup', methods=['GET', 'POST'])
def createGroup():
    username = get_username()
    
    inGroup = in_group(username)
    isMgr = getIsMgr(username, inGroup, request)
    isOwner = getIsOwner(username, inGroup, request=request)

    # names = {"bob", "joe", "jill", username}
    names = get_all_users()
    try:
        names.remove(username)
    except:  # remove method errors if element not within
        ()

    if request.method == 'GET':

        html = render_template('createGroup.html', names=names, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner)
        response = make_response(html)
        return response

    else:
        gName = request.form['gName']
        groupId = add_group(username, gName, None)
        for name in names:
            selected = request.form.get(name) is not None
            if selected:
                add_user_to_group(groupId, name, 'member')
        response = redirect(url_for('manage'))
        response.set_cookie('groupname', gName)
        response.set_cookie('groupid', str(groupId))
        return response


@app.route('/newuser', methods=['GET', 'POST'])
def newuser():
    username = get_username()

    if user_exists(username):
        return redirect(url_for('profile'))

    html = render_template('newuser.html')
    response = make_response(html)
    return response

@app.route('/createProfile', methods=['GET', 'POST'])
def createProfile():
    username = get_username()

    if user_exists(username):
        return redirect(url_for('profile'))

    if request.method == 'GET':
        if (user_exists(username)):
            return redirect(url_for('profile'))
        html = render_template('createProfile.html', schedule=blankSchedule(), inGroup=False, isMgr=False, isOwner=False, editable=True)
        response = make_response(html)
        return response

    else:
        fname = request.form['fname']
        lname = request.form['lname']

        email = request.form['email']

        # notification preferences default to false currently - can change if wanted
        prefemail = False

        globalPreferences = parseSchedule()

        groupid = 1 # for prototype - add user to group one
        if not (user_exists(username)):
            add_user(fname, lname, username, email, create_preferences(globalPreferences))
            add_user_to_group(groupid, username, "member", prefemail, create_preferences(globalPreferences))
        else:
            update_profile_info(fname, lname, username, email, create_preferences(globalPreferences))

        return redirect(url_for('profile'))

@app.route('/editProfile',methods=['GET','POST'])
def editProfile():
    username = get_username()

    inGroup = in_group(username)
    isMgr = getIsMgr(username, inGroup, request)
    isOwner = getIsOwner(username, inGroup, request=request)
    userInfo = get_profile_info(username)
    prevfirstName = userInfo.firstname
    prevlastName = userInfo.lastname
    prevemail = userInfo.email

    prevGlobalPreferences = blankSchedule()
    try:
        prevGlobalPreferences = get_double_array(get_global_preferences(username))
    except Exception:
        pass

    if request.method == 'GET':
        html = render_template('editProfile.html', prevfname=prevfirstName, prevlname=prevlastName, \
            prevemail=prevemail, schedule=prevGlobalPreferences, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner, editable=True)
        response = make_response(html)
        return response

    else:
        if request.form["submit"] == "Save Information":
            fname = request.form['fname']
            lname = request.form['lname']
            email = request.form['email']

            update_profile_info(fname, lname, username, email, create_preferences(prevGlobalPreferences))

            html = render_template('editProfile.html', prevfname=fname, prevlname=lname, \
                prevemail=email, schedule=prevGlobalPreferences, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner,editable=True)
        if request.form["submit"] == "Save Preferences":
            globalPreferences = parseSchedule()
           
            update_profile_info(prevfirstName, prevlastName, username, prevemail, create_preferences(globalPreferences))

            html = render_template('editProfile.html', prevfname=prevfirstName, prevlname=prevlastName, \
                prevemail=prevemail, schedule=globalPreferences, inGroup=inGroup, isMgr=isMgr, isOwner=isOwner,editable=True)
        
        response = make_response(html)
        return response

if __name__ == '__main__':
    app.run()
