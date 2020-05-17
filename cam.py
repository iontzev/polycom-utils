import curses
from curses import panel
import json
import paramiko
import re
import time

class CameraPosition(object):
    def __init__(self, settings, stdscreen):
        self.window = stdscreen.subwin(0, 0)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

        self.selected_device = 0
        self.settings = settings
        self.position = [0, 0, 0]
        self.connected = None

    def navigate(self, n):
        self.selected_device += n
        if self.selected_device < 0:
            self.selected_device = 0
        elif self.selected_device >= len(self.devices):
            self.selected_device = len(self.devices) - 1

    def printPosition(self):
        self.window.addstr(5, 0, f'Camera position:')
        self.window.addstr(6, 2, f'pan  {self.position[0]}          ')
        self.window.addstr(7, 2, f'tilt {self.position[1]}          ')
        self.window.addstr(8, 2, f'zoom {self.position[2]}          ')

    def displayInfo(self):
        self.window.addstr(0, 0, 'Polycom utilites. Camera control')
        self.window.addstr(1, 0, 'Developed by Iontzev (iontzev@gmail.com)')
        self.window.addstr(19, 0, 'Press d to select device for connecting')
        self.window.addstr(20, 0, 'Press q to quit')
        if self.connected:
            self.window.addstr(3, 0, f'Connected to {self.connected["username"]}@{self.connected["address"]}:{self.connected["port"]} ({self.connected["name"]})')
            self.window.addstr(16, 0, f'Use arrows keys for pan/tilt and plus/minus keys for zoom (step: {self.settings["step"]})')
            self.window.addstr(17, 0, 'Press r to get camera position')
            self.window.addstr(18, 0, 'Press s to input step value')

    def run(self):
        # Clear screen
        self.window.clear()
        # Hide cursor
        curses.curs_set(0)
        flag_exit = False
        flag_connect = False
        while not flag_exit:
            if flag_connect:
                try:
                    with open("settings/devices.json") as json_data_file:
                        self.devices = json.load(json_data_file)
                except:
                    self.devices = []
                self.devices.append({'name': 'exit', 'address': 'return to main window'})
                self.selected_device = min(self.selected_device, len(self.devices) - 1)
                self.displayMenu()
                if self.connected:
                    flag_connect = False
                
            self.displayInfo()
            if not self.connected:
                while True:
                    key = self.window.getch()
                    if key == ord("q"):
                        flag_exit = True
                        break
                    elif key == ord("d"):
                        flag_connect = True
                        break
            else:
                with self.client.invoke_shell() as ssh:
                    self.getInfo(ssh)
                    self.displayInfo()
                    while True:
                        key = self.window.getch()
                        if key == ord("q"):
                            flag_exit = True
                            break
                        elif key == ord("d"):
                            flag_connect = True
                            break
                            continue
                        elif key == ord("s") and self.connected:
                            self.inputStep()
                            self.displayInfo()
                            self.printPosition()
                            continue
                        elif key == curses.KEY_RIGHT:
                            self.position[0] += self.settings["step"]
                        elif key == curses.KEY_LEFT:
                            self.position[0] -= self.settings["step"]
                        elif key == curses.KEY_UP:
                            self.position[1] += self.settings["step"]
                        elif key == curses.KEY_DOWN:
                            self.position[1] -= self.settings["step"]
                        elif key == 43:
                            self.position[2] += self.settings["step"]
                        elif key == 45:
                            self.position[2] -= self.settings["step"]
                        elif key == ord('r'):
                            self.getPosition(ssh)
                            self.printPosition()
                            continue
                        else:
                            continue
                        self.setPosition(ssh)
                        self.printPosition()

    def displayMenu(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()

        while True:
            self.window.refresh()
            curses.doupdate()
            self.window.addstr(1, 0, 'Select device:')
            for index, item in enumerate(self.devices):
                if index == self.selected_device:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL

                msg = item['name'] + ' (' + item['address'] + ')'
                self.window.addstr(2 + index, 1, msg, mode)
            self.window.addstr(4 + len(self.devices), 0, 'For changing device list edit file settings/devices.json')

            key = self.window.getch()

            if key in [curses.KEY_ENTER, ord("\n")]:
                if self.selected_device == len(self.devices) - 1:
                    break
                else:
                    self.connected = self.connect(self.devices[self.selected_device])
                    if not self.connected:
                        self.window.clear()
                        self.window.addstr(0, 0, 'Failed to connecting to ' + self.devices[self.selected_device]['name'])
                        self.window.addstr(1, 0, 'Press any key to return to main menu')
                        self.window.getch()
                    break

            elif key == curses.KEY_UP:
                self.navigate(-1)

            elif key == curses.KEY_DOWN:
                self.navigate(1)

            elif key == 27: # Escape
                break

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()

    def inputStep(self):
        self.window.clear()
        self.window.addstr(0, 0, 'Input step (value from 1 to 1000 and press Enter: ')
        # Show cursor
        curses.curs_set(1)
        curses.echo()
        step = ''
        while True:
            key = self.window.getch()
            if key == 27: #Escape
                break
            elif key in [curses.KEY_ENTER, ord("\n")]:
                try:
                    step = int(step)
                    if step>0 and step<=1000:
                        self.settings['step'] = step
                        break
                except:
                    pass
                self.window.addstr(0, 0, 'Input step (value from 0 to 1000 and press Enter: ')
                self.window.clrtoeol()
                step = ''
            else:
                step += chr(key) 
        # Hide cursor
        curses.curs_set(0)
        curses.noecho()
        self.window.clear()

    def connect(self, device):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.position = [0, 0, 0]
        try:
            client.connect(hostname=device['address'], username=device['username'], password=device['password'], port=device['port'], timeout=5)
            self.client = client
            return device
        except:
            self.client = None

    def getInfo(self, ssh):
        time.sleep(0.5)
        result = ssh.recv(5000)

    def getPosition(self, ssh):
        command = 'camera near getposition\n' 
        ssh.send(command)
        time.sleep(0.2)
        try:
            result = ssh.recv(5000).decode('ascii')
        except:
            result = ''
        if result[0:23] == 'camera near getposition':
            pos = re.findall(r'[-+]?[.]?[\d]+(?:,\d\d\d)*[\.]?\d*(?:[eE][-+]?\d+)?', result)
            if len(pos) == 3:
                self.position = [int(p) for p in pos]

    def setPosition(self, ssh):
        command = f'camera near setposition {self.position[0]} {self.position[1]} {self.position[2]}\r' 
        ssh.send(command)
        time.sleep(0.2)
        ssh.recv(500).decode('ascii')

class ScreenApp(object):
    def __init__(self, stdscreen, settings):
        self.screen = stdscreen
        cam = CameraPosition(settings, self.screen)
        cam.run()

if __name__ == "__main__":
    try:
        with open("settings/settings.json") as json_data_file:
            settings = json.load(json_data_file)
    except:
        settings = {'step': 100}

    curses.wrapper(ScreenApp, settings)

