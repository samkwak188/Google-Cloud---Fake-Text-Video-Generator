This is another version of Fake Text Story Generator, where this version uses Google Cloud Storage to store the background videos. This way video handling is more efficient and faster. However, Render free tier has not enough memory even for this method. I'm still working on how to deploy my pyhton app as website. Until then, you can refer to this [Github repository](https://github.com/samkwak188/Fake-Text-Video-Generator/tree/main) to download codes yourself and run it on your own local server. The link to preset videos can be found [here](https://drive.google.com/drive/folders/1lu_HuPx0Tkpa6w7N-8zQUdPmch9Kr-tY?usp=sharing). Save the videos under static - videos folder. 

Note: For the `GOOGLE_CREDENTIALS`, you need to:
1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Copy the entire contents of the JSON file as a single line
4. Paste it as the value for GOOGLE_CREDENTIALS

The bucket should contain the following background videos:
- background.mp4
- background_1.mp4
- background_2.mp4
- background_3.mp4
- background_4.mp4

As I mentioned earlier, the preset videos can be found [here](https://drive.google.com/drive/folders/1lu_HuPx0Tkpa6w7N-8zQUdPmch9Kr-tY?usp=sharing).
