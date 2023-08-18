---
title: MCR Video Setup ({{ date | date('dddd, MMMM Do') }})
assignees: recc-tech
---

# MCR Setup Checklist

- Turn everything on.
    - [ ] Turn on camera 4 (the camera on the tripod).
    - [ ] Turn on the sound computer.
    - [ ] Open last week's preset in vMix.
    - [ ] Turn on both monitors in the MCR and activate the external output in vMix.
    - [ ] Turn on the NDI controller.
- Download assets from Planning Center Online and import into vMix.
    - [ ] Download the Kids Connection Video, sermon notes (if they're present), and any other new assets (e.g., new bumper videos, new announcements).
    - [ ] Move the Kids Connection video and sermon notes to `D:\Users\Tech\Documents\vMix Assets\By Service\YYYY-MM-DD`, where `YYYY-MM-DD` is today's date.
    - [ ] Move the other new assets to `D:\Users\Tech\Documents\vMix Assets\By Type\`.
    - [ ] Import the Kids Connection video into the "Videos" category in vMix and close the previous week's video.
        - You can drag and drop videos directly from Windows File Explorer into vMix!
    - [ ] Import the other new assets into vMix.
    - [ ] If you have time, clear out outdated files. For each outdated file, close the input in vMix and move the file to `D:\Users\Tech\Documents\vMix Assets\By Type\Archive\`.
- Check that the events are set up properly on Church Online Platform.
    - [ ] Check that the main event and rebroadcast events have been created _and have content_. If not, follow the instructions for [creating events on Church Online Platform](https://github.com/recc-tech/tech/wiki/Creating-Events-on-Church-Online-Platform).
    - [ ] Copy the sermon notes to the event (if they were on Planning Center Online).
        > :warning: Pay attention to the "Additional Services" section at the end.
        > - For the main event, uncheck every other service.
        > - For the rebroadcasts, check all the other rebroadcasts on the same date but uncheck everything else.
- Check that the events are set up properly on BoxCast.
    - [ ] Check that both the Kids Connection and the main event have been created. If not, follow the instructions for [creating live events on BoxCast](https://github.com/recc-tech/tech/wiki/Creating-Live-Events-on-BoxCast).
- Set up and test triggers for Kids Connection countdown and video. This lets you set up in the Annex while the Kids Connection countdown and video play automatically.
    - [ ] Set up a trigger on the kids countdown loop that fades to the kids video for this week.
    - [ ] Set up a trigger on the kids video that fades to the pre-stream title loop.
    - [ ] Test the triggers by playing the countdown loop and video (skip to a few seconds before the end).
- [ ] Restart all videos and loops. Do this _after_ testing the triggers so that you don't forget to reset those videos.
- Update the titles in vMix.
    - [ ] Pre-stream title
    - [ ] Host
    - [ ] Speaker
    - [ ] Special announcer(s), if any
    - [ ] Check that all the titles and the pre-stream title loop look good.
- [ ] Create backup slides for the message notes and verses. See the [guide to generating backup slides](https://github.com/recc-tech/tech/wiki/Generating-Backup-Slides).
- [ ] Save the vMix preset as a new file. Click "Save As" and name the file `YYYY-MM-DD Live.vmix` (where `YYYY-MM-DD` is today's date).
- [ ] Check the cameras. If any of the band members are in a bad position (e.g., blocking someone else), ask them to move. If the cameras are laggy or unresponsive, see https://github.com/recc-tech/tech/wiki/MCR-Visuals-Troubleshooting#the-cameras-arent-working.
- [ ] Check that vMix is receiving sound from the MCR sound station. If not, see https://github.com/recc-tech/tech/wiki/MCR-Visuals-Troubleshooting#theres-no-sound-coming-from-the-sound-station.
- [ ] Once it's time for the Kids Connection broadcast, mute other sounds (LR on the sound computer and the NDI source), play the 5 minute countdown, _and start the stream_. Check in Church Online Platform's Host Tools that the stream is working.
- Set up the Kids Connection tech in the Annex.
    - [ ] Copy the kids video to the laptop's Desktop. You can use the USB from the MCR sound station, as long as you put it back when you're done.
    - [ ] Once the kids broadcast starts, bring the equipment to the Annex and set up the laptop and TV.
        - On the old Dell Latitude, you should be able to log in to the account `David Reader` without a password.
        - On the old Dell Inspiron, use the account `Tech`. The password should be written on a sticky note on the laptop. If for some reason you need the security questions, the answers are all "Montreal".
- [ ] After the Kids Connection broadcast, start recording.

## General Reminders
- At each scene change (e.g., from worship to announcements):
    - Put up the person's title up
    - Check the sound level
