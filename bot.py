import telegram
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, ConversationHandler
import requests
import re
from telegram.ext.filters import Filters
from telegram import InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

import json 
import mysql.connector 

#######################################################
key = "SECRET_BOT_API_KEY"

WAITINGCOURSECODE = 0
WAITINGCOURSENO = 1
ADDEDCOURSE = 2
WAITINGDELETEDCOURSE = 3


# Loading json
f = open("data.json")
data = json.loads(f.read())
f.close()

# Database connection
db = mysql.connector.connect(
  host="localhost",
  user="root",
  password="DB_PASSWORD",
  database = "Offerings"
)

cursor = db.cursor()


dept_list = []

for i in data["depts"]:
    dept_list.append(i["code"])

# Start conversation, force user to start a new schedule
def start(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text = "Welcome to Bilkent Offerings Bot.")
    context.bot.send_message(chat_id=update.message.chat_id, text = "You can plan your schedule here.")
    
    cursor.execute("select * from Users where chatID = " + str(update.message.chat_id))
    results = cursor.fetchall()
    
    if len(results) == 0:
        cursor.execute("INSERT INTO Users(chatID, name) VALUES(%s, %s);", (update.message.chat_id, update.message.from_user.first_name))
        db.commit()
    
    ik = ReplyKeyboardMarkup.from_button(KeyboardButton(text = "/newschedule"))
    context.bot.send_message(chat_id=update.message.chat_id, text = "Select an option.", reply_markup = ik)

# Delete previous schedule data. 
def newschedule(update, context):
    # Database sil
    cursor.execute("DELETE FROM Schedules WHERE chatID = " + str(update.message.chat_id))
    db.commit()
    
    context.bot.send_message(chat_id=update.message.chat_id, text = "Your old schedule is deleted and a new one is started.")
    menuu(update, context)

def addcourse(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text = "Adding new course.")
    
    buttons = [["/cancel"]]
    for i in dept_list:
        buttons.append([i])
    ik = ReplyKeyboardMarkup(buttons)
    context.bot.send_message(chat_id=update.message.chat_id, text = "Select a department.", reply_markup = ik)
    return WAITINGCOURSECODE

def addcoursecode(update, context):
    buttons = [["/cancel"]]
    
    for i in data["depts"]:
        if i["code"] == update.message.text:
            for j in i["courses"]:
                buttons.append([update.message.text + " " + str(j["no"])])
    ik = ReplyKeyboardMarkup(buttons)
    context.bot.send_message(chat_id=update.message.chat_id, text = "Select a course.", reply_markup = ik)
    return WAITINGCOURSENO

def addcourseno(update, context):
    course_c = update.message.text.split()[0]
    course_n = update.message.text.split()[1]
    cursor.execute("SELECT * FROM Schedules WHERE chatID = %s AND courseCode = %s AND courseNo = %s", (update.message.chat_id, course_c, course_n))
    results = cursor.fetchall()
    
    if len(results) == 0:
        cursor.execute("INSERT INTO Schedules(chatID, courseCode, courseNo) VALUES(%s, %s, %s);", (update.message.chat_id, course_c, course_n))
        db.commit()
        context.bot.send_message(chat_id=update.message.chat_id, text = "Added course " + update.message.text )
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text = "Course " + update.message.text + " is already in your list." )

    menuu(update, context)
    return ConversationHandler.END
   
def menuu(update, context):
    
    cursor.execute("SELECT * FROM Schedules WHERE chatID = " + str(update.message.chat_id))
    courses = cursor.fetchall()
    
    buttons = [["/addcourse"]]
    
    if len(courses) == 0:
        context.bot.send_message(chat_id=update.message.chat_id, text = "You have no courses yet." )
    else:
        buttons.append(["/delcourse"])
        buttons.append(["/execute"])
        courses_message = "Your current courses are: \n"
        
        for i in courses:
            courses_message += i[1] + " " + str(i[2]) + "\n"
            
        context.bot.send_message(chat_id=update.message.chat_id, text = courses_message )
        
    buttons.append(["/newschedule"])
    ik = ReplyKeyboardMarkup(buttons)
    context.bot.send_message(chat_id=update.message.chat_id, text = "Select an option.", reply_markup = ik)

def delcourse(update, context):
    cursor.execute("SELECT * FROM Schedules WHERE chatID = " + str(update.message.chat_id))
    courses = cursor.fetchall()
    
    buttons = [["/cancel"]]
    for i in courses: 
        buttons.append([i[1] + " " + str(i[2])])
    
    ik = ReplyKeyboardMarkup(buttons)
    context.bot.send_message(chat_id=update.message.chat_id, text = "Select a course to delete", reply_markup = ik)
    
    return WAITINGDELETEDCOURSE

def delcoursedone(update, context):
    cursor.execute("DELETE FROM Schedules WHERE chatID = %s AND courseCode = %s AND courseNo = %s", (update.message.chat_id, update.message.text.split()[0], update.message.text.split()[1] ))
    db.commit()
    context.bot.send_message(chat_id=update.message.chat_id, text = "Deleted course " + update.message.text)
    menuu(update,context)
    return ConversationHandler.END

# This function checks whether a lecture starting at s1s and ending at s1e conflicting with a lecture
# starting at s2s and ending at s2e.
def check_conflict_from_time(s1s, s1e, s2s, s2e):
    if s1s > s2e or s2s > s1e:
        return False
    return True

# Checking the conflicts for two section objects.
def check_conflict(s1, s2):
        for i in s1["hours"]:
            for j in s2["hours"]:
                if i["day"] != j["day"]:
                    continue
                if check_conflict_from_time(i["start_time"], i["end_time"], j["start_time"], j["end_time"]):
                    return True
        return False

# Recursive function to find all possible combinations.
def find_possibilities(sections):
    if len(sections) == 1:
        results = []
        for i in sections[0]:
            results.append([])
            results[-1].append(i)
        # print(results)
        return results
    
    current_results = find_possibilities(sections[:-1])
    results = []
    for i in current_results:
        for j in sections[-1]:
            #print(i)
            checking = i + [j]
            bb = True
            for k in checking[:-1]:
                if check_conflict(k, checking[-1]):
                    bb = False
                    break
            if bb:
                results.append(checking)
    return results

# Generation of the output html report.
def generate_html(courses, possibilities, last_pull):       
           
    top_str = "<!DOCTYPE html><html><head><title>"
    top_str += "Auto Generated Schedule Possibilities Report</title></head><body>"
    top_str += "<h1>Auto Generated Schedule Combinations Report</h1>"
    top_str += "<h3>Generated By Telegram Bot "
    top_str += "<a href=\"https://t.me/BilkentOfferingsBot\">"
    top_str += "@BilkentOfferingsBot</a></h3>"
    top_str += "<h3><a href=\"https://t.me/BilkentOfferingsBot\">GitHub</a></h3>"
    top_str += "<h4>Based on the data from %s</h4><br></br>" % last_pull
    
    option_no = 1
    for possibility in possibilities:
        schedule = []
    
        for i in range(14):
            schedule.append([])
            for j in range(7):
                schedule[i].append("")
        xx = 0
        for i in possibility:
            
            for j in i["hours"]:
                lecture_no = (j["start_time"] - 510)/60
                for k in range(int((j["end_time"]+10-j["start_time"])/60)):
                    cell_content = courses[xx][0] + str(courses[xx][1]) + "-" + str(i["no"]) + "|" + j["place"]
                    schedule[int(lecture_no)][int(j["day"])] = cell_content 
                    lecture_no += 1
            xx += 1
        
        #print(schedule)
        
        table_str = ("<h2>Option %s:</h2>" % option_no)
        table_str += "<ol>"
        
        cno = 0
        for i in courses:
            table_str += "<li>"
            
            table_str += "%s%s-%s|%s" % (i[0], i[1], possibility[cno]["no"], possibility[cno]["instructor"])
            table_str += "</li>"
            cno += 1
        table_str += "</ol>"
        table_str += "<table border=\"1\" table-layout: fixed>"
        table_str += '''<tr>
        <th>Time</th>
        <th>Monday</th>
        <th>Tuesday</th>
        <th>Wednesday</th>
        <th>Thursday</th>
        <th>Friday</th>
        <th>Saturday</th>
        <th>Sunday</th>
        </tr>'''
        
        for i in range(14):
            table_str += "<tr>"
            table_str += "<td>"
            table_str += str(i+8) + ".30" + "-" + str(i+9) + ".20" 
            table_str += "</td>"
            for j in range(7):
                table_str += "<td>"
                table_str += schedule[i][j]
                table_str += "</td>"
            table_str += "</tr>"
            
        table_str += "</table>"
    
        top_str += table_str
        option_no += 1
    top_str += "</body></html>"
    return top_str

# execution command given by user
def execute(update, context):
    cursor.execute("SELECT courseCode, courseNo from Schedules where chatID = " + str(update.message.chat_id))
    user_courses = cursor.fetchall()
    #print(user_courses)
    sections = []
    
    for i in user_courses:
        for j in data["depts"]:
            if j["code"] == i[0]:
                for k in j["courses"]:
                    if k["no"] == i[1]:
                        sections.append(k["sections"])
    
    
    possibilities = find_possibilities(sections)
    
    f = open("max_no.txt", "r")
    max_no = int(f.read())
    f.close()
    
    f = open("max_no.txt", "w")
    f.write(str(max_no + 1))
    f.close()
    
    f = open( "report%s.html" % str(max_no + 1), "w")
    f.write(generate_html(user_courses, possibilities, data["pull_time"]))
    f.close()
    
    context.bot.sendDocument(chat_id=update.message.chat_id, document=open("report%s.html" % str(max_no + 1), 'rb'))
    final_message = "Here is your file. Thanks for using @BilkentOfferingsBot."
    context.bot.send_message(chat_id=update.message.chat_id, text = final_message)
    menuu(update, context)
    
def cancel(update, context):
    context.bot.send_message(chat_id=update.message.chat_id, text = "Cancelled. Going back to main menu.")
    menuu(update, context)

# API specific stuff

updater = Updater(key)
dp = updater.dispatcher

conv_handler_add = ConversationHandler(
    entry_points=[CommandHandler('addcourse', addcourse)],
    states = {
        WAITINGCOURSECODE : [MessageHandler(Filters.text & ~Filters.command, addcoursecode)],
        WAITINGCOURSENO : [MessageHandler(Filters.text & ~Filters.command, addcourseno)],
        ADDEDCOURSE : [MessageHandler(Filters.text & ~Filters.command, menuu)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)

conv_handler_del = ConversationHandler(
    entry_points=[CommandHandler('delcourse', delcourse)],
    states = {
        WAITINGDELETEDCOURSE : [MessageHandler(Filters.text & ~Filters.command, delcoursedone)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)

dp.add_handler(conv_handler_add)
dp.add_handler(conv_handler_del)


dp.add_handler(CommandHandler('start',start))
dp.add_handler(CommandHandler('help',help))
dp.add_handler(CommandHandler('newschedule',newschedule))
#dp.add_handler(CommandHandler('addcourse',addcourse))
dp.add_handler(CommandHandler('delcourse',delcourse))
dp.add_handler(CommandHandler('menu',menuu))
dp.add_handler(CommandHandler('execute',execute))

#dp.add_handler(CommandHandler('contact',contact))
#dp.add_handler(CommandHandler('donate',donate))
#dp.add_handler(MessageHandler(Filters.text, url))

updater.start_polling()
updater.idle()
