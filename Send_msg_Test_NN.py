from pythonosc.udp_client import SimpleUDPClient
UDP_IP = "127.0.0.1"
UDP_PORT = 12000

# FORMAT
# chords_message = [[Chord, timestamp]]
# strum_message = [["DOWN"/"UP"], timestamp]
# pluck_message = [[note (midi value), duration, speed, timestamp]]

#chords_message = [["C", 0.0], ["G", 1.0], ["A", 2.0], ["F", 3.0]]
chords_message = [["C", 0.0]]
#strum_message = [["DOWN", 0.0], ["UP", 1.0], ["DOWN", 2.0], ["UP", 3.0]]
strum_message = [["DOWN", 0.0]]
# pluck_message = [[45, 1, 1, 1], [45, 1, 2, 2], [45, 1, 3, 3], [45, 1, 4, 4], [45, 1, 5, 5],
#                 [45, 1, 6, 6], [45, 1, 7, 7], [45, 1, 8, 8], [45, 1, 9, 9], [45, 1, 10, 10]]

# pluck_message = [[45, 1, 10, 1],[51, 1, 4, 1.5], [45, 1, 5, 3], [51, 1, 8, 3.5], [45, 1, 5, 5.0], [51, 1.5, 8, 5.5],
 #                [45, 1, 10, 7],[51, 1, 4, 7.5], [45, 1, 5, 9], [51, 1, 8, 9.5], [45, 1, 5, 11], [51, 1.5, 8, 11.5],
  #               [45, 1, 10, 13],[51, 1, 4, 13.5], [45, 1, 5, 15], [51, 1, 8, 15.5], [45, 1, 5, 17], [51, 1.5, 8, 17.5]]

pluck_message = [[45, 5, 3, 1]]

def send_osc_message(client, address, data):
    print(f"Sending OSC message to {address}: {data}")
    client.send_message(address, data)

def main():
    # Create an OSC client
    client = SimpleUDPClient(UDP_IP, UDP_PORT)
    send_osc_message(client, "/Chords", chords_message)
    send_osc_message(client, "/Strum", strum_message)
    send_osc_message(client, "/Pluck", pluck_message)


if __name__ == "__main__":
    main()