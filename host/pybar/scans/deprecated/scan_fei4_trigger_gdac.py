import time
import logging
import math
import numpy as np
import tables as tb
from threading import Event
from scipy.interpolate import interp1d

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils, make_box_pixel_mask_from_col_row

from daq.readout import data_dict_list_from_data_dict_iterable, is_data_from_channel


def get_gdacs(thresholds, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['mean_threshold'], mean_threshold_calibration['gdac'], kind='slinear', bounds_error=True)
    return np.unique(interpolation(thresholds).astype(np.uint32))


class Fei4TriggerGdacScan(ScanBase):
    scan_id = "scan_fei4_trigger_gdac"

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        config_file_trigger_fe : config file name for the second Fe that is used to trigger the first Fe
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.
        '''

        logging.info('Start GDAC source scan from %d to %d in %d steps' % (np.amin(gdac_range), np.amax(gdac_range), len(gdac_range)))
        logging.info('Estimated scan time %dh' % (len(gdac_range) * self.scan_timeout / 3600.))

        self.stop_loop_event = Event()
        self.stop_loop_event.clear()

        self.configure_triggered_fe()
        self.configure_trigger_fe(config_file_trigger_fe, self.col_span, self.row_span)

        wait_for_first_trigger_setting = self.wait_for_first_trigger  # needed to reset this for a new GDAC

        with open_raw_data_file(filename=self.scan_data_filename + "_trigger_fe", title=self.scan_id, scan_parameters=["GDAC"]) as raw_data_file_trigger_fe:
            with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, scan_parameters=["GDAC"]) as raw_data_file:
                for gdac_value in gdac_range:
                    if self.stop_thread_event.is_set():
                        break
                    self.stop_loop_event.clear()
                    self.register_utils.set_gdac(gdac_value)
                    self.readout.start()
                    wait_for_first_trigger = wait_for_first_trigger_setting
                    # preload command
                    lvl1_command = self.register.get_commands("zeros", length=14)[0] + self.register.get_commands("LV1")[0]  # + self.register.get_commands("zeros", length=1000)[0]
                    self.register_utils.set_command(lvl1_command)
                    # setting up external trigger
                    self.dut['tlu'].RESET
                    self.dut['tlu']['TRIGGER_MODE'] = 0
                    self.dut['cmd']['EN_EXT_TRIGGER'] = True

                    show_trigger_message_at = 10 ** (int(math.ceil(math.log10(self.max_triggers))) - 1)
                    last_iteration = time.time()
                    saw_no_data_at_time = last_iteration
                    saw_data_at_time = last_iteration
                    scan_start_time = last_iteration
                    no_data_at_time = last_iteration
                    time_from_last_iteration = 0
                    scan_stop_time = scan_start_time + self.scan_timeout
                    current_trigger_number = 0
                    last_trigger_number = 0
                    while not self.stop_loop_event.is_set() and not self.stop_thread_event.wait(self.readout.readout_interval):
                        current_trigger_number = self.dut['tlu']['TRIGGER_COUNTER']
                        if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
                            logging.info('Collected triggers: %d', current_trigger_number)
                        last_trigger_number = current_trigger_number
                        if self.max_triggers is not None and current_trigger_number >= self.max_triggers:
                            logging.info('Reached maximum triggers. Stopping Scan...')
                            self.stop_loop_event.set()
                        if scan_start_time is not None and time.time() > scan_stop_time:
                            logging.info('Reached maximum scan time. Stopping Scan...')
                            self.stop_loop_event.set()
                        time_from_last_iteration = time.time() - last_iteration
                        last_iteration = time.time()
                        while True:
                            try:
                                data = self.readout.data.popleft()
                                raw_data_trigger_fe = data_dict_list_from_data_dict_iterable(data_dict_iterable=(data,), filter_func=is_data_from_channel(self.channel_trigger_fe))
                                raw_data_fe = data_dict_list_from_data_dict_iterable(data_dict_iterable=(data,), filter_func=is_data_from_channel(self.channel_triggered_fe))
                                raw_data_file.append(raw_data_fe, scan_parameters={"GDAC": gdac_value})
                                raw_data_file_trigger_fe.append(raw_data_trigger_fe, scan_parameters={"GDAC": gdac_value})

                            except IndexError:  # no data
                                no_data_at_time = last_iteration
                                if wait_for_first_trigger is False and saw_no_data_at_time > (saw_data_at_time + self.timeout_no_data):
                                    logging.info('Reached no data timeout. Stopping Scan...')
                                    self.stop_loop_event.set()
                                elif wait_for_first_trigger is False:
                                    saw_no_data_at_time = no_data_at_time

                                if no_data_at_time > (saw_data_at_time + 10):
                                    scan_stop_time += time_from_last_iteration
                                break  # jump out while loop

                            saw_data_at_time = last_iteration

                            if wait_for_first_trigger is True:
                                logging.info('Taking data...')
                                wait_for_first_trigger = False

                    self.dut['cmd']['EN_EXT_TRIGGER'] = False
                    self.dut['tlu']['TRIGGER_MODE'] = 0

                    logging.info('Total amount of triggers collected: %d for GDAC %d' % (self.dut['tlu']['TRIGGER_COUNTER'], gdac_value))

                    self.readout.stop()

                    raw_data_trigger_fe = data_dict_list_from_data_dict_iterable(data_dict_iterable=self.readout.data, filter_func=is_data_from_channel(self.channel_trigger_fe))
                    raw_data_fe = data_dict_list_from_data_dict_iterable(data_dict_iterable=self.readout.data, filter_func=is_data_from_channel(self.channel_triggered_fe))
                    raw_data_file.append(raw_data_fe, scan_parameters={"GDAC": gdac_value})
                    raw_data_file_trigger_fe.append(raw_data_trigger_fe, scan_parameters={"GDAC": gdac_value})

    def configure_trigger_fe(self, config_file_trigger_fe, col_span, row_span):
        logging.info("Sending configuration to trigger FE")
        self.register_trigger_fe = FEI4Register(config_file_trigger_fe)
        self.register_utils_trigger_fe = FEI4RegisterUtils(self.dut, self.readout, self.register_trigger_fe)
        self.register_utils_trigger_fe.configure_all(same_mask_for_all_dc=True)

        commands = []
        # generate ROI mask for Enable mask
        pixel_reg = "Enable"
        mask = make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands.extend(self.register_trigger_fe.get_commands("ConfMode"))
        enable_mask = np.logical_and(mask, self.register_trigger_fe.get_pixel_register_value(pixel_reg))
        self.register_trigger_fe.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register_trigger_fe.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # generate ROI mask for Imon mask
        pixel_reg = "Imon"
        mask = make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
        imon_mask = np.logical_or(mask, self.register_trigger_fe.get_pixel_register_value(pixel_reg))
        self.register_trigger_fe.set_pixel_register_value(pixel_reg, imon_mask)
        commands.extend(self.register_trigger_fe.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register_trigger_fe.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register_trigger_fe.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register_trigger_fe.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register_trigger_fe.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        # set trigger latency and replication
        self.register_trigger_fe.set_global_register_value("Trig_Lat", 222)  # set trigger latency
        self.register_trigger_fe.set_global_register_value("Trig_Count", 4)  # set number of consecutive triggers
        commands.extend(self.register_trigger_fe.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        # setting FE into RunMode
        commands.extend(self.register_trigger_fe.get_commands("RunMode"))
        self.register_utils_trigger_fe.send_commands(commands)

    def configure_triggered_fe(self):
        logging.info("Sending configuration to triggered FE")
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # disable hitbus
        pixel_reg = "Imon"
        self.register.set_pixel_register_value(pixel_reg, 1)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        # # set trigger latency and replication
        self.register.set_global_register_value("Trig_Lat", 221)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", 4)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        # setting FE into RunMode
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        output_file_trigger_fe = self.scan_data_filename + "_trigger_fe_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.max_tot_value = 13
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename, maximum='maximum')
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + "_trigger_fe.h5", analyzed_data_file=output_file_trigger_fe) as analyze_raw_data:
            analyze_raw_data.max_tot_value = 13
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename + '_trigger_fe', maximum='maximum')


if __name__ == "__main__":
    import configuration
    import os

    config_file_triggered_fe = os.path.join(os.getcwd(), r'config/fei4/configs/SCC_99_low_thr_tuning.cfg')  # Chip 1, GA 1
    config_file_trigger_fe = os.path.join(os.getcwd(), r'config/fei4/configs/SCC_30_tuning.cfg')  # Chip 2, GA 2
#     gdac_range = range(100, 5001, 15)  # GDAC range set manually

    # GDAC settings can be set automatically from the calibration with equidistant thresholds
    input_file_calibration = 'data/calibrate_threshold_gdac_SCC_99.h5'  # the file with the GDAC <-> PlsrDAC calibration
    threshold_range = np.arange(19, 280, 0.8)  # threshold range in PlsrDAC to scan
    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        gdac_range = get_gdacs(threshold_range, in_file_calibration_h5.root.MeanThresholdCalibration[:])

    scan = Fei4TriggerGdacScan(**configuration.default_configuration)  # configuration of triggered FE
    scan.start(use_thread=True, restore_configuration=True, gdac_range=gdac_range, config_file_trigger_fe=config_file_trigger_fe, col_span=[25, 55], row_span=[50, 250], timeout_no_data=1 * 60, scan_timeout=100, max_triggers=10000000, channel_triggered_fe=4, channel_trigger_fe=3, invert_lemo_trigger_input=True)
    scan.stop()
