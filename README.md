### Blender 4.0+ Fork

This is a fork of the 2.8 fork, which was a fork of the original 2.77 version of this plugin. Some features may not work, but basic mesh importing should be functional in Blender 4.0.

Mesh and sequence importing for this fork was designed specifically to import Onverse dts/dsq files. It may or may not work for dts/dsq files from other games.

---

Leaving this here for potential maintainers or onlookers:  
DTS specification: https://web.archive.org/web/20200906020103/http://docs.garagegames.com/torque-3d/official/content/documentation/Artist%20Guide/Formats/dts_format.html  
DSQ specification: https://web.archive.org/web/20200906020104/http://docs.garagegames.com/torque-3d/official/content/documentation/Artist%20Guide/Formats/dsq_format.html  

---

\\!/ WARNING \\!/ YOU ARE ABOUT TO READ IMPORTANT INFORMATION!

Groups are now collections. If you want to have a collision group, just make a new collection and link your collision meshes to that collection. For instance:

![LOS collision](https://bansheerubber.com/i/f/YyseE.png)

Constitutes a valid LOS collision collection.

![Normal collision](https://bansheerubber.com/i/f/GRLrn.png)

Constitutes a valid normal collision collection. The same principle applies to detail groups. A collection named detail9999 will have all of its objects only visible in first person.

---
# BRAND NEW!

Visibility animations are here, thanks to a guest appearance from irrelevant.irreverent. Visibility animations are cool. They allow objects' transparency to be animated. The most famous example of this is the default rocket launcher's explosion shape. If you pay close attention, it fades out as it expands.  

NOW YOU CAN HARNESS THIS POWER USING THESE SIMPLE STEPS!:

1. Like the rest of animations, this is done through empties. If you select an empty you want to visibilityify, you can go to its **Object Properties** to start animating away.  
![Blessing of Jim](https://bansheerubber.com/i/f/nxWKI.png)
2. To animate this property, hover over it and press **i** on your keyboard. BE CAREFUL! If you are not, you will be suprised to see it start glowing a **Yellow Color**. If you glance over to your **Graph Editor**, you will see that you have added a keyframe. Keep adding more keyframes by advancing to subsequent frames and pressing **I** over and over again. Once completed, you should have a beautiful curve of your choosing.  
![Fear Simi](https://bansheerubber.com/i/f/buteO.png)
3. Ta-dah! You're done. It's as simple as that. It should be noted this also works for importations as well. You should see a similar curve appear whenever a shape has a visibility animation. If one does not appear, please call the police and file a **Missing Curves Report** immediately.  
4. A preview of the animation I created during these steps can be viewed here https://youtu.be/98RmuQ6sJRk. Another thing you should be aware of is visibility animations are strange. To get the best milage out of them, make sure to check the **Use Transparency** option under the animated object's materials. Otherwise, they will blink abruptly in and out as they are animated in-game.  

I don't think there's any other differences. GO MAKE THINGS!!!!!!!
