import logging
import threading
import system_modules.ChatSpeechProcessor as csp
import system_modules.ConnectionStatus as cs
import system_modules.ContextHandlers as ch
import system_modules.SoundManager as sm
import system_modules.Chat as chat
import system_modules.LoadTts as loadtts
import modules.DaisyMethods as dm
import ModuleLoader as ml

import modules.RgbLed as led


class Daisy:
	description = "Provides a user flow for Chat"
	module_hook = "Main_start"

	def __init__(self):
		self.daisy_stop_event = threading.Event()
		self.awake_stop_event = threading.Event()

		self.csp = csp.instance
		self.cs = cs.instance
		self.ch = ch.instance
		self.sounds = sm.instance
		self.chat = chat.instance
		self.dm = dm.instance
		self.ml = ml.instance

		self.led = led.instance

		self.internet_warning_logged = False
		self.tts = None

	def close(self):
		self.daisy_stop_event.set()

	def main(self):
		self.sounds.play_sound("beep", 0.5)
		print("🌼DAISY🌼")
		threads = []

		# Create the TtsThread instance and start it in time for when it's needed
		t = loadtts.LoadTts(self)
		threads.append(t)
		t.start()

		# Check for Internet connection
		self.awake_stop_event.clear()
		t = threading.Thread(target=self.cs.check_internet, args=(self.daisy_stop_event, self.awake_stop_event))
		threads.append(t)
		t.start()

		while not self.daisy_stop_event.is_set():

			self.led.turn_on_color(0, 100, 0)  # Solid Green

			awake = self.dm.listen_for_daisy_wake(self.daisy_stop_event, self.awake_stop_event)

			self.led.breathe_color(100, 100, 100)  # Breathe Blue

			if awake:
				# Check for "Daisy Cancel" sleep word
				dc_thread = threading.Thread(target=self.dm.listen_for_daisy_cancel, args=(self.daisy_stop_event, self.awake_stop_event))
				threads.append(dc_thread)
				dc_thread.start()

				# HOOK: Daisy_wake
				try:
					hook_instances = self.ml.hook_instances
					if "Daisy_wake" in hook_instances:
						Daisy_wake_instances = hook_instances["Daisy_wake"]
						for instance in Daisy_wake_instances:
							logging.info("Running Daisy_start module: "+type(instance).__name__)
							response_text = instance.main()
				except Exception as e:
					logging.warning("Daisy_wake Hook: "+str(e))

				while not self.daisy_stop_event.is_set() and not self.awake_stop_event.is_set():
					self.led.breathe_color(0, 0, 100)  # Breathe Blue
					stt_text = self.csp.stt(self.awake_stop_event, 30, 'alert') # 30-second timeout
					logging.info("STT DONE")

					if self.awake_stop_event.is_set() or not stt_text:
						break

					self.led.breathe_color(100,0,100)  # Breathe Blue #NEEDS CANCEL LOOP

					self.ch.add_message_object('user', stt_text)

					sound_stop_event = threading.Event()
					self.sounds.play_sound_with_thread('waiting', 0.2, self.awake_stop_event, sound_stop_event)

				   
					try:
						context = self.ch.get_context_without_timestamp()
						text = self.chat.request(context, self.awake_stop_event, sound_stop_event, self.tts)
					except Exception as e:
						logging.error("Daisy request error: "+ e)
						self.awake_stop_event.set()
						break

					if not text:
						logging.error("Daisy request error: No response")
						self.awake_stop_event.set()
						break

					self.ch.add_message_object('assistant', text)

					self.chat.display_messages()
					if self.awake_stop_event.is_set():
						break

					self.led.breathe_color(100, 100, 100)  # Breathe White

				dc_thread.join()
				self.sounds.play_sound_with_thread('end', 1.0)

		for t in threads:
			t.join()