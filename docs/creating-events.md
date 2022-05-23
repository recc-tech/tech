# Creating BoxCast and Church Online Platform Events (Live-type)

This guide is meant to structure the creation of new events on the BoxCast and Church Online Platform. If you would like to create new events for __rebroadcast-type events__, click [here]().

## BoxCast
1. Go to the "New Broadcast" section.
2. Create events for the kids service.
	1. Name the event `Kids Connection LIVE: [date]`. The `[date]` will automatically be replaced by the date of the event.
	2. Make the event recurring on a weekly basis
	3. Set the start time to 10:00 and the end time to 10:25.
	4. Set the video quality to 1080p @30fps.
	5. Set the source to "Primary RECC Stream."
	6. Check the "Enable Live-Only" box.
3. Create events for the main service.
	1. Name the event `Sunday Gathering LIVE: [date]`. The `[date]` will automatically be replaced by the date of the event.
	2. Make the event recurring on a weekly basis
	3. Set the start time to 10:25 and the end time to 11:40.
	4. Set the video quality to 1080p @30fps.
	5. Set the source to "Primary RECC Stream."
4. The events should now be visible in the BoxCast dashboard.

> :warning: __Important!__  \
> Facebook, YouTube, and any other destinations should only be added for the event that will contain the Sunday Gathering content. Do ___not___ add them for any event thay contains Children's Ministry content. This is due to a licensing conflict. The copyright holders only allow us to stream such content to our own website. 

> :warning: __Important!__  \
> Do ___not___ check the "Enable Live-Only" box when creating the main service. If you enable that option, BoxCast will not record the event as the broadcast progresses. The upshot will be that you will have to upload a local recording, BoxCast will have to transcode this recording, and it will take much longer to set up the rebroadcasts. For example, it will take approximately 20 minutes to upload a local recording, and as transcoding is a 1:1 process it will take at least as long as the local recording's file length for it to be ready for rebroadcast. 

## Church Online Platform
1. Go to the "Services" tab in admin mode. 

![COP Interface 1](https://user-images.githubusercontent.com/43655839/169702280-85f3473f-221a-4934-8009-336523a97dd1.png)

2. Click on "add service time" to create an event

![COP Interface 2](https://user-images.githubusercontent.com/43655839/169703130-37db37ff-af65-4b74-a223-7fab03b37859.png)

3. Create a new event starting at 10:05. Define the date and how the event should repeat. 
4. Once the event is created, click on "edit content."
5. First, give the event a title. Then, define an appropriate duration, ensure public chat is active, and that the chat is active 5 minutes before and after the event. 

![COP Interface 3](https://user-images.githubusercontent.com/43655839/169707820-96886f13-1a9b-4f94-8bae-fb1123e2b963.png)

> :warning: __Important!__  \
> When you define before and after event times for when public chat is active, those values shift the start and end time of the event by the value defined. For example, a 10:05 start time becomes 10:00. 

6. Define the event's video source. Ensure the "embed code" radio button is active. 

![COP Interface 4](https://user-images.githubusercontent.com/43655839/169722573-7c5ad75b-f8d5-4e32-9050-fbe466458326.jpg)

Currently, the global embed code for all events received and transcoded by BoxCast is the following:

`<div id="boxcast-widget-dihucxlq2coankbx2iko"></div><script type="text/javascript" charset="utf-8">(function(d, s, c, o) {var js = d.createElement(s), fjs = d.getElementsByTagName(s)[0];var h = (('https:' == document.location.protocol) ? 'https:' : 'http:');js.src = h + '//js.boxcast.com/v3.min.js';js.onload = function() { boxcast.noConflict()('#boxcast-widget-'+c).loadChannel(c, o); };js.charset = 'utf-8';fjs.parentNode.insertBefore(js, fjs);}(document, 'script', 'dihucxlq2coankbx2iko', {"showTitle":0,"showDescription":0,"showHighlights":0,"showRelated":false,"defaultVideo":"next","market":"unknown","showDocuments":false,"showIndex":false,"showDonations":false}));</script>`

This global embed code can be found on the BoxCast platform:

	1. Go to the "Embed Media" section on BoxCast.
	2. Select "JavaScript" and "Player."
	3. Copy the embed code.

> :warning: __Important!__  \
> Also, ensure that the video starts at least 5 minutes before the service begins. This is so that the five minute countdown is streamed to end users, and so that those who attend the online event early have something to watch. Even if no content is being actively received and transcoded by boxcast, the embed code is dynamic and will inform users that the stream has not yet started, but will momentarily. 

For our purposes, the event has been sufficiently configured. At the scheduled time, the event will "open" and will pass through the embedded live stream to viewers. Only those viewers who have made an account on the platform will be able to participate in the event's public chat. 

If you would like to learn more about the other configuration options available on the platform, please click [here](https://support.online.church/l/en) and reference their support documentation. 

