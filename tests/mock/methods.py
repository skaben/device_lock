#    def mock_serial_read(self, mock_port, data_queue):
#        while self.running:
#            if not mock_port.empty():
#                serial_data = mock_port.get()
#                if serial_data:
#                    data_queue.put(serial_data)
