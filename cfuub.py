#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
2015
	Currently in testing and rewrite!
	Migration to WMFlabs
	Swap calls to Pywikibot (core)
	Add logs to http://tools-static.wmflabs.org/commonsfairuseupload/
	Bot flags requested on en.wp and commons
	Author: Fae
	License: CC-BY-SA-4.0

2012
	Creation
	https://github.com/wikigit/Commons-fair-use-upload-bot/blob/master/Commons_fair_use_upload_bot.py
	Author: Dcoetzee
"""

#import mwclient
import pywikibot
from pywikibot import pagegenerators
from pywikibot import Category
import ConfigParser
import re
import sys
import time
import urllib
import os, stat

def myprint(str):
	# When stdout is redirected to a log file, we have to choose an encoding.
	print(str.encode('utf-8', 'strict'))

def allow_bots(text, user):
	if (re.search(r'\{\{(nobots|bots\|(allow=none|deny=.*?' + user + r'.*?|optout=all|deny=all))\}\}', text)):
		return False
	return True

def is_commons_admin(user):
	# No API to determine if a user is an administrator, use urllib
	# ugh
	params = urllib.urlencode({'title': 'Special:ListUsers', 'limit': 1, 'username': user.encode("utf-8")})
	opener = MyURLopener()
	f = opener.open("http://commons.wikimedia.org/w/index.php?%s" % params)
	return re.search('<a href="/wiki/Commons:Administrators" title="Commons:Administrators">administrator</a>', f.read())

def download_to_file(page, filename):
	url = pywikibot.page.FilePage(sitecommons, page.title()).fileUrl()
	urllib.urlretrieve(url, filename)		# reporthook would be nice here, just in case some are very large

def format_time(time):
	return '%d-%02d-%02d %02d:%02d:%02d UTC' % \
		   (time.tm_year, time.tm_mon, time.tm_mday, time.tm_hour, time.tm_min, time.tm_sec)

def contains_template(template_name, text):
	# Use IGNORECASE to catch redirects with alternate capitalizations
	# TODO: Catch all redirects accurately
	return re.search(r'{{' + template_name + r'[^}]*}}\s*', text, re.IGNORECASE)

def remove_template(template_name, text):
	# Use IGNORECASE to catch redirects with alternate capitalizations
	# TODO: Catch all redirects accurately
	return re.sub(r'(?i){{' + template_name + r'[^}]*}}\s*', '', text, re.IGNORECASE)

# Gets argument of a one-argument template (with optional default argument name 1)
def get_template_arg(template_name, text):
	# Use IGNORECASE to catch redirects with alternate capitalizations
	# TODO: Catch all redirects accurately
	# TODO: Generalize to retrieving dictionary of all template arguments
	m = re.search(r'{{' + template_name + r'\|(1=)?([^}]*)}}', text, re.IGNORECASE)
	if m:
		return m.group(2)
	else:
		return None

def describe_file_history(sitename, filepage):
	# TODO: localize this based on sitename
	desc = "\n\n== Wikimedia Commons file description page history ==\n"
	# CONVERT THIS
	for revision in filepage.revisions(prop = 'timestamp|user|comment|content'):
		desc += "* " + format_time(revision['timestamp']) + " [[:commons:User:" + revision['user'] + "|" + revision['user'] + "]] ''<nowiki>" + revision['comment'] + "</nowiki>''\n"
	return desc


# CONVERT THIS
def describe_upload_log(sitename, filepage):
	# TODO: localize this based on sitename
	desc = "\n== Wikimedia Commons upload log ==\n"
	for imagehistoryentry in filepage.imagehistory():
		desc += "* " + format_time(imagehistoryentry['timestamp']) + " [[:commons:User:" + imagehistoryentry['user'] + "|" + imagehistoryentry['user'] + "]] " + str(imagehistoryentry['width']) + "&times;" + str(imagehistoryentry['height']) + " (" + str(imagehistoryentry['size']) + " bytes) ''<nowiki>" + imagehistoryentry['comment'] + "</nowiki>''\n"
	return desc

def get_user_who_added_template(template, filepage):
	taguser = "?"; prevuser = "?"
	for revision in filepage.fullVersionHistory():
		# revision format [id, timestamp, user, content]
		if taguser == '?' and not re.search(r'{{' + template + r'[^}]*}}\s*', revision[3], re.IGNORECASE):
			taguser = prevuser
		prevuser = revision[2]
	return taguser

def get_request_fair_use_template(reason):
	reason_arg = "|reason=" + reason if reason else ''
	return '{{Request fair use delete' + reason_arg + "}}\n\n"

def get_candidate_template(sitename, reason):
	reason_arg = "|reason=" + reason if reason else ''
	lang = sitename[0]
	if lang == 'en':
		return "{{Fair use candidate from Commons|" + filepage.title() + reason_arg + "}}\n\n"
	elif lang == 'et':
		return "{{Mittevaba_pildi_kandidaat_Commonsist|" + filepage.title() + reason_arg + "}}\n\n"

def get_local_tags(sitename, historyinfo):
	desc = ''
	if (sitename == ['en','wikipedia']):
		desc += "{{di-no fair use rationale|date=" + time.strftime("%d %B %Y", time.gmtime()) + "}}\n"
		if historyinfo['width'] > 400:
			desc += "{{Non-free reduce}}\n"
	return desc

def get_local_tags_pd_us(sitename, historyinfo):
	desc = ''
	if (sitename == ['en','wikipedia']):
		desc += "{{PD-US-1923-abroad}}\n"
	else:
		desc += "{{PD-US}}\n"
	return desc

def get_notification(sitename, filepage):
	lang = str.split(sitename, '.')[0]
	if lang == 'en':
		return '{{subst:Fair use candidate from Commons notice|' + filepage.title() + '}} ~~~~'
	elif lang == 'et':
		return '{{subst:Kasutusel_mittevaba_pildi_kandidaat|' + filepage.title() + '}} ~~~~'

def get_notification_summary(sitename, filepage):
	lang = str.split(sitename, '.')[0]
	# TODO: localize
	return 'Bot notice: Fair use candidate from Commons: ' + filepage.title()

def get_install_redirect_summary(sitename):
	# TODO: localize
	return 'Bot creating image redirect to local re-upload of image being deleted at Commons'

def append_to_filename(suffix, filename):
	return re.sub(r'^File:(.*)\.([^.]*)$', r'\1' + suffix + r'.\2', filepage.title())

class MyURLopener(urllib.FancyURLopener):
	version = 'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US; rv:1.9.2.4) Gecko/20100527 Firefox/3.6.4'

myprint('Starting Commons fair use upload bot run at ' + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
sys.stdout.flush()

logyear = time.strftime("%Y", time.gmtime())
logname =  "Commons_fair_use_upload_bot_"+ logyear + ".html"
logpath = "/data/project/commonsfairuseupload/www/static/"
log = ""
commonsuserlink = "http://commons.wikimedia.org/wiki/User:"
commonsimagelink = "https://commons.wikimedia.org/wiki/"

supported_wikis = [
	['et', 'wikipedia'],
	['en', 'wikipedia'],
	['en', 'wikibooks']
	]

pd_us_wikis = [
	['en', 'wikipedia'], 
	['en', 'wikisource'], 
	['', 'wikisource']
	]

sitecommons = pywikibot.Site('commons', 'commons')

#dry_run = False
dry_run = True

categorytitle = u'Pending fair use deletes'
category = pywikibot.Category(sitecommons, categorytitle)
gen = pagegenerators.CategorizedPageGenerator(category, recurse=True)

for filepage in gen:
	if filepage.namespace() != 6:
		continue
	myprint(filepage.title())
	sys.stdout.flush()
	# Could use imagepage.getFileVersionHistory()[-1]['descriptionurl']
	download_to_file(filepage, '/tmp/downloadedfile')
	filedescription = filepage.get()
	if not contains_template('Fair use delete', filedescription):
		myprint('No Fair use delete tag found for ' + filepage.title())
		continue
	reason = get_template_arg('Fair use delete', filedescription)

	for s in ['Fair use delete', 'Delete', 'delete', 'Copyvio', 'copyvio']:
		filedescription = remove_template(s, filedescription)

	taguser = get_user_who_added_template('Fair use delete', filepage)
	if not is_commons_admin(taguser):
		logline = 'Request was made by non-admin user <a href="{0}{1}">{1}</a>'.format(commonsuserlink, taguser.encode('utf-8')) + ' for <a href="{}{}">{}</a>'.format(commonsimagelink, re.sub(" ", "_", filepage.title().encode('utf-8')), filepage.title().encode('utf-8')) + ', replacing with {{Request fair use delete}}'
		myprint(logline.decode('utf-8', 'ignore'))
		log += '\n<tr><td>' + time.strftime("%Y-%m-%d&nbsp;%H:%M", time.gmtime()) + '<td>' + logline
		filedescription = get_request_fair_use_template(reason) + filedescription
		if not dry_run:
			filepage.put(filedescription, summary = '{{tl|Fair use delete}} tag must be placed by an admin, changing to {{tl|Request fair use delete}}')
		else:
			myprint("New file description:\n" + filedescription)
		continue
	myprint('Tag added by administrator ' + taguser)

	imagepage = pywikibot.page.FilePage(sitecommons, filepage.title())
	historyinfo = imagepage.getFileVersionHistory()[-1]		# Most recent data
	# key: comment, sha1, url, timestamp, metadata, height, width, mime, user, descriptionurl, size

	uploaded_sites = []
	for sitename in supported_wikis:
		site = pywikibot.Site(sitename[0], sitename[1])

		filepagelocal = pywikibot.Page(site, filepage.title())
		usage = pagegenerators.ReferringPageGenerator(filepagelocal, followRedirects=True)
		if len(list(usage)) == 0: 
			continue

		uploaded_sites.append(sitename)
		newdesc = get_local_tags(sitename, historyinfo) + \
				  get_candidate_template(sitename, reason) + \
				  filedescription + \
				  describe_file_history(sitename, filepage) + \
				  describe_upload_log(sitename, filepage) + \
				  "__NOTOC__\n"
		newfilename = append_to_filename(' - from Commons', filepage.title())
		myprint('Uploading /tmp/downloadedfile to ' + newfilename)
		sys.stdout.flush()
		if not dry_run:
			site.upload(open('/tmp/downloadedfile'), newfilename, newdesc, ignore=True)
		# We upload at a new name and redirect to get around permission limitations on some (all?) wikis
		# which prevent uploading over files still present at Commons.
		if not dry_run:
			filepagelocal.save('#REDIRECT[[File:' + newfilename + ']]', summary = get_install_redirect_summary(sitename))

		for page in filepagelocal.imageusage(namespace=0):
			myprint('In use on page ' + page.name + ' on ' + sitename)
			talkpage = site.Pages['Talk:' + page.name]
			text = talkpage.edit()
			if allow_bots(text, 'Commons fair use upload bot'):
				myprint('Updating talk page ' + talkpage.name + ' with notice')
				sys.stdout.flush()
				if not dry_run:
					talkpage.save(text + "\n" + get_notification(sitename, filepage), summary = get_notification_summary(sitename, filepage))
				else:
					myprint("Notification:\n" + get_notification(sitename, filepage))
					myprint("Edit summary: " + get_notification_summary(sitename, filepage))

	myprint('Marking file for speedy deletion...')
	sys.stdout.flush()
	speedyreason = reason if reason else 'Marked for deletion.'
	if not re.search(r'\.$', speedyreason):
		speedyreason += '.'
	if len(uploaded_sites) > 0:
		speedyreason += " Copies uploaded to " + str.join(', ', uploaded_sites) + " as fair use candidates."
	filedescription = "{{speedydelete|" + speedyreason + "}}\n\n" + filedescription
	if not dry_run:
		filepage.save(filedescription, summary = 'Finished uploading fair use image to local projects, marking for speedy deletion')
	else:
		myprint("New file page:\n" + filedescription)
	myprint('Done.')

categorytitle = u'Category:Images in the public domain in the United States but not the source country'
category = Category(sitecommons, categorytitle)
gen = pagegenerators.CategorizedPageGenerator(category, recurse=True)

for filepage in gen:
	if filepage.namespace() != 6:
		continue
	myprint(filepage.title())
	sys.stdout.flush()
	download_to_file(filepage, '/tmp/downloadedfile')
	filedescription = filepage.edit()
	if not contains_template('PD-US-1923-abroad-delete', filedescription):
		myprint('No PD-US-1923-abroad-delete tag found for ' + filepage.title())
		continue
	reason = get_template_arg('PD-US-1923-abroad-delete', filedescription)

	for s in ['PD-US-1923-abroad-delete', 'PD-US', 'PD-1923', 'PD-US-1923', 'PD-pre-1923', 'PD-pre1923', 'Delete', 'delete', 'Copyvio', 'copyvio']:
		filedescription = remove_template(s, filedescription)

	taguser = get_user_who_added_template('PD-US-1923-abroad-delete', filepage)
	if not is_commons_admin(taguser):
		myprint('Request was made by non-admin user "' + taguser.encode('ascii', 'ignore') + '" for ' + filepage.title() + ', replacing with {{Request fair use delete}}')
		filedescription = get_request_fair_use_template(reason) + filedescription
		if not dry_run:
			filepage.save(filedescription, summary = '{{tl|PD-US-1923-abroad-delete}} tag must be placed by an admin, changing to {{tl|Request fair use delete}}')
		else:
			myprint("New file description:\n" + filedescription)
		continue
	myprint('Tag added by administrator ' + taguser)

	historyinfo = filepage.imagehistory().next()

	#site = mwclient.Site('et.wikipedia.org')
	#site.login(username, password)
	#filepagelocal = site.Images[filepage.page_title]
	#if len(list(filepagelocal.imageusage())) > 0:
		#myprint('Skipping (User:Commons fair use upload bot]] does not yet have upload privileges on etwiki)')
		#continue

	uploaded_sites = []
	for sitename in pd_us_wikis:
		site = mwclient.Site(sitename)
		site.login(username, password)

		filepagelocal = site.Images[filepage.page_title]
		if len(list(filepagelocal.imageusage())) == 0:
			continue

		uploaded_sites.append(sitename)
		newdesc = get_local_tags_pd_us(sitename, historyinfo) + \
				  filedescription + \
				  describe_file_history(sitename, filepage) + \
				  describe_upload_log(sitename, filepage) + \
				  "__NOTOC__\n"
		newfilename = append_to_filename(' - from Commons', filepage.title())
		myprint('Uploading /tmp/downloadedfile to ' + newfilename)
		sys.stdout.flush()
		if not dry_run:
			site.upload(open('/tmp/downloadedfile'), newfilename, newdesc, ignore=True)
		# We upload at a new name and redirect to get around permission limitations on some (all?) wikis
		# which prevent uploading over files still present at Commons.
		if not dry_run:
			filepagelocal.save('#REDIRECT[[File:' + newfilename + ']]', summary = get_install_redirect_summary(sitename))

	myprint('Marking file for speedy deletion...')
	sys.stdout.flush()
	speedyreason = reason if reason else 'Marked for deletion.'
	if not re.search(r'\.$', speedyreason):
		speedyreason += '.'
	if len(uploaded_sites) > 0:
		speedyreason += " Copies uploaded to " + str.join(', ', uploaded_sites) + " as public domain in US but not source country."
	filedescription = "{{speedydelete|" + speedyreason + "}}\n\n" + filedescription
	if not dry_run:
		filepage.save(filedescription, summary = 'Finished uploading public-domain-in-US-only image to local projects, marking for speedy deletion')
	else:
		myprint("New file page:\n" + filedescription)
	myprint('Done.')

myprint('Run completed at ' + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "\n")

myprint('Log\n' + log.decode('utf-8'))

loghead = '''<html>
<meta http-equiv="Content-type" content="text/html; charset=utf-8" />
<style>
table {background-color: silver;}
td {border: 2px solid grey;background-color: lightgreen;}
</style>
<body><h1>''' + logyear + ''' log for Commons fair use upload bot</h1>
<p>This bot is currently in a trial mode, so this log is illustrative using test log entries and may not be accurate!</p>
<table>'''
logtail = "</table>\n</body></html>"

if os.path.isfile(logpath + logname):
	logfile = open(logpath + logname, "r+")
	html = logfile.read()
	if len(html)>10:
		logold = html.split('<table>')[1].split('</table>')[0]
	else:
		logold = ""
	logfile.close()	# Ensure overwrite
	logfile = open(logpath + logname, "w")
	logfile.write( loghead + logold + log + logtail )
	logfile.close()
else:                    
	myprint("Creating log at "+ logpath+logname)
	logfile = open(logpath + logname, "w")
	logfile.write( loghead + log + logtail )
	logfile.close()
	os.chmod(logpath + logname, stat.S_IWUSR | stat.S_IRUSR | stat.S_IROTH)
