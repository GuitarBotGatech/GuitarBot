1. Get rid of unnecessary bridge for UI -> python code. Use HTTP to send JSON directly.
- In this version, dont include any of the tone master stuff so that the UI -> python is simple: POST /play and POST /reset only

2. Go over the existing MIDI -> guitarbot JSON format and build it into a single python file that takes midi and a settings config file and outputs the guitarbot json format. 

3. make JSON = Events list

4. Go over path planner

5. Go over chord selector

6. GuitarBotParser