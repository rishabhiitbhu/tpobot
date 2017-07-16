from __future__ import absolute_import, unicode_literals
from celery.utils.log import get_task_logger
from celery import shared_task
import requests
import logging
import json
from wit import Wit
from wit.wit import WitError
from collections import defaultdict

from tpobot.settings import AT, wit_server_AT
from bot.models import User, Company
from bot.messages import *
from bot.intentParser import *

logger = get_task_logger(__name__)

client = Wit(access_token=wit_server_AT)

entityTypes = {

    'intent': Intent(),
    'greetings': Greeting(),
    'question': Question(),

}
#get the intent
def call_wit(msg):
    logging.info('\ncalling wit for %s' %msg)
    try:
        resp = client.message(msg)
        return (resp['entities'], True)
    except WitError as e:
        logging.info('Got WitError %s \n' %e)
        return ({'e': e}, False)



@shared_task
def completeProfile(psid, received_msg):
    user = User.objects.get(psid=psid)
    received_msg = received_msg.strip().split(' ')
    if len(received_msg) != 1:
        msg = message_dict['reg_error']
        return send_msg(psid, msg)
        

    value = received_msg[0].lower()

    if '@' in value and user.email is None:#it's email and user hasn't set it yet
        if 'itbhu.ac.in' in value:
            temp = value.split('@')[0].split('.')[-1]
            if len(temp) != 5: #like eee15
                msg = message_dict['invalid_email']
                return send_msg(psid, msg)
                
            user.department = temp[:3]#eee
            user.email = value
            user.save()
            msg = message_dict['email_set'].format(value)
            send_msg(psid, msg)
            msg = message_dict['get_course']
            return send_msg(psid, msg)
            
        else:
            msg = message_dict['not_iit_email']
            return send_msg(psid, msg)
            

    elif (value=='idd' or value=='btech' or value=='imd') and \
                                user.course is None and user.email:
        #true when email is set, course isn't, you got a valid value

        user.course = value
        user.profile_completed = True
        user.save()
        msg = message_dict['course_set'].format(value)
        send_msg(psid, msg)
        msg = message_dict['reg_success']
        send_msg(psid, msg)
    else:
        msg = message_dict['reg_error']
        return send_msg(psid, msg)
        

#will use graph API to save few user fields, rest to be asked in complete profile function
@shared_task
def newUser(psid):
    url = 'https://graph.facebook.com/v2.6/{0}?fields=first_name,last_name,'\
            'profile_pic,locale,timezone,gender&access_token={1}'
    url = url.format(psid, AT)
    # logging.info(url)
    response = requests.get(url)
    data = response.json()
    logging.info('Got response of graph API, code: ' + str(response.status_code))
    first_name = data['first_name']
    last_name = data['last_name']
    profile_pic = data['profile_pic']
    gender = data['gender']
    logging.info('New User %s %s' %(first_name, last_name))
    user = User.objects.create(psid=psid, 
                                    first_name = first_name, 
                                    last_name = last_name, 
                                    gender = gender, 
                                    profile_pic = profile_pic)

    msg = message_dict['welcome']
    send_msg(psid, msg)
    msg = message_dict['get_email']
    send_msg(psid, msg)


@shared_task
def analyseMessage(psid, message):
    response, status = call_wit(message)
    logging.info('wit response: %s\n' % dict(response))
    msg_sent_count = 0
    if status:
        #entity like `intent`, `greetings`, `question` etc
        for entity in response:
            logging.info('responseType %s\n' % str(responseType))
            entityClass = entityTypes[responseType]
            logging.info('Enitity Class: %s\n' % entityClass.__class__.__name__)
            #every entity has a list of entity types like my `intent` has `happiness` 
            for entityType in response[entity]:
                logging.info('Checking entityType: %s\n' % entityType)
                method = getattr(entityClass, entityType['value'])
                logging.info('Calling method: %s\n' % method.__name__)
                msgSent = method(psid, entityType['confidence'])
                msg_sent_count += bool(msgSent)

    else:#WitError
        msg = message_dict['wit_error']
        msgSent = send_msg(psid, msg)
        msg_sent_count += bool(msgSent)        

    logging.info("msg_sent_count: %s\n" % msg_sent_count)
    if msg_sent_count == 0:
        msg = message_dict['no_idea']
        send_msg(psid, msg)


@shared_task
def informUsersAboutNewCompany(company_name):
    company = Company.objects.get(company_name=company_name)
    msg = message_dict['new_company'].format(
                    company.company_name,
                    company.course,
                    company.department,
                    company.btech_ctc,
                    company.idd_imd_ctc,
                    company.x,
                    company.xii,
                    company.cgpa,
                    company.status,
                )
    for user in User.objects.all():
        if (user.course in company.course) and \
                (user.department in company.department):
                send_msg(user.psid, msg)
    
@shared_task
def updateUserAboutThisCompany(company_name, data_dict, changed_fields):
    company = Company.objects.get(company_name=company_name)
    msg = message_dict['updated_company'].format(company_name)
    for field in changed_fields:
        msg += field + ": " + data_dict[field] + "\n"

    msg += "\n\nThis is it for now.\nCya :)"
    for user in User.objects.filter(subscribed=True):
        if (user.course in company.course) and \
            (user.department in company.department):
            send_msg(user.psid, msg)
