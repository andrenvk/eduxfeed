# eduxfeed

_Keeps you up to date with Edux updates_

At [FIT CTU](https://fit.cvut.cz/) we use [Edux](https://edux.fit.cvut.cz/) system to support the studying process. For each subject, one can find there course requirements, study materials, classification, etc. But it is not easy for a student to follow all the changes during a semester as new stuff can be added and/or updated any time. There should be one (_and preferably only one_) place to go to to find out what has changed. That place is __eduxfeed__.

### Project
Edux is based on [DokuWiki](https://www.dokuwiki.org) and as such provides [syndication](https://www.dokuwiki.org/syndication). The idea is to use news feeds which come with each subject and use them to create a student-specific feed with all the informantion relevant to him or her. This will be a web service, the student will log in through an [auth server](https://auth.fit.cvut.cz/), the app will read student's info using [KOSapi](https://kosapi.fit.cvut.cz/) and allow additional config of the resulting feed.

### Features
* Enrolled subjects are automatically subscribed
* Possibility to add or remove other subjects from subscription
* Namespace filtering (i.e. Czech students are not interested in /en/ namespace for English version of a particular subject)
* Merging multiple changes and providing additional info such as author, time, diff
* Mark-as-read mechanism for each feed item (see Challenges)

### Challenges
* Access to course pages is based on ACL with [many different roles](https://edux.fit.cvut.cz/prezentace/2009-06-25#uzivatelske_role_a_pristupova_prava)
* Users don't provide login informantion directly to the app, but authorized access to Edux is required to get all the info needed 
* Default feeds seem not informing about changes to files (when a file is updated, but the filename remains unchanged)
* A page can be updated multiple times before the student checks the feed, but the feed should merge all the changes into one feed item, but how to know that this feed item was already read? A solution can be a mark-as-read action on the item.
* Setting up a job scheduler or similar technique to crawl Edux feeds regularly
