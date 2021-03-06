import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, data_array_from_data_iterable, get_col_row_array_from_data_record_array
from pybar.analysis.plotting.plotting import plotThreeWay


class GdacTuning(Fei4RunBase):
    '''Global Threshold Tuning

    Tuning the global threshold to target threshold value (threshold is given in units of PlsrDAC).
    The tuning uses a binary search algorithm.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "scan_parameters": [('GDAC', None)],
        "target_threshold": 50,  # target threshold in PlsrDAC to tune to
        "gdac_tune_bits": range(7, -1, -1),  # GDAC bits to change during tuning
        "n_injections_gdac": 50,  # number of injections per GDAC bit setting
        "max_delta_threshold": 2,  # minimum difference to the target_threshold to abort the tuning
        "mask_steps_gdac": 3,  # mask
        "enable_mask_steps_gdac": [0],  # mask steps to do per GDAC setting
        "plot_intermediate_steps": False,  # plot intermediate steps (takes time)
        "plots_filename": None,  # file name to store the plot to, if None show on screen
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        if not self.plots_filename:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
            self.close_plots = True
        else:
            self.close_plots = False
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=self.mask_steps_gdac)[0]

        self.write_target_threshold()
        for gdac_bit in self.gdac_tune_bits:  # reset all GDAC bits
            self.set_gdac_bit(gdac_bit, bit_value=0)

        additional_scan = True
        last_bit_result = self.n_injections_gdac
        decreased_threshold = False  # needed to determine if the FE is noisy
        all_bits_zero = True

        def bits_set(int_type):
            int_type = int(int_type)
            count = 0
            position = 0
            bits_set = []
            while(int_type):
                if(int_type & 1):
                    bits_set.append(position)
                position += 1
                int_type = int_type >> 1
                count += 1
            return bits_set

        # calculate selected pixels from the mask and the disabled columns
        select_mask_array = np.zeros(shape=(80, 336), dtype=np.uint8)
        if not self.enable_mask_steps_gdac:
            self.enable_mask_steps_gdac = range(self.mask_steps_gdac)
        for mask_step in self.enable_mask_steps_gdac:
            select_mask_array += make_pixel_mask(steps=self.mask_steps_gdac, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        occupancy_best = 0
        vthin_af_best = self.register.get_global_register_value("Vthin_AltFine")
        vthin_ac_best = self.register.get_global_register_value("Vthin_AltCoarse")
        for gdac_bit in self.gdac_tune_bits:

            if additional_scan:
                self.set_gdac_bit(gdac_bit)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, bit %d = 1' % (scan_parameter_value, gdac_bit))
            else:
                self.set_gdac_bit(gdac_bit, bit_value=0)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, bit %d = 0' % (scan_parameter_value, gdac_bit))

            with self.readout(GDAC=scan_parameter_value):
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections_gdac, mask_steps=self.mask_steps_gdac, enable_mask_steps=self.enable_mask_steps_gdac, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=True, mask=None, double_column_correction=self.pulser_dac_correction)

            self.raw_data_file.append(self.fifo_readout.data, scan_parameters=self.scan_parameters._asdict())

            occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
            self.occ_array_sel_pixel = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by creating a mask
            median_occupancy = np.ma.median(self.occ_array_sel_pixel)
            if abs(median_occupancy - self.n_injections_gdac / 2) < abs(occupancy_best - self.n_injections_gdac / 2):
                occupancy_best = median_occupancy
                vthin_af_best = self.register.get_global_register_value("Vthin_AltFine")
                vthin_ac_best = self.register.get_global_register_value("Vthin_AltCoarse")

            if self.plot_intermediate_steps:
                plotThreeWay(self.occ_array_sel_pixel.transpose(), title="Occupancy (GDAC " + str(scan_parameter_value) + " with tuning bit " + str(gdac_bit) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)

            if abs(median_occupancy - self.n_injections_gdac / 2) < self.max_delta_threshold and gdac_bit > 0:  # abort if good value already found to save time
                logging.info('Median = %f, good result already achieved (median - Ninj/2 < %f), skipping not varied bits' % (median_occupancy, self.max_delta_threshold))
                break

            if median_occupancy == 0 and decreased_threshold and all_bits_zero:
                logging.info('FE noisy?')

            if gdac_bit > 0:
                if (median_occupancy < self.n_injections_gdac / 2):  # set GDAC bit to 0 if the occupancy is too lowm, thus decrease threshold
                    logging.info('Median = %f < %f, set bit %d = 0' % (median_occupancy, self.n_injections_gdac / 2, gdac_bit))
                    self.set_gdac_bit(gdac_bit, bit_value=0)
                    decreased_threshold = True
                else:  # set GDAC bit to 1 if the occupancy is too high, thus increase threshold
                    logging.info('Median = %f > %f, leave bit %d = 1' % (median_occupancy, self.n_injections_gdac / 2, gdac_bit))
                    decreased_threshold = False
                    all_bits_zero = False

            if gdac_bit == 0:
                if additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    last_bit_result = self.occ_array_sel_pixel.copy()
                    self.gdac_tune_bits.append(0)  # bit 0 has to be scanned twice
                else:
                    last_bit_result_median = np.median(last_bit_result[select_mask_array > 0])
                    logging.info('Scanned bit 0 = 0 with %f instead of %f' % (median_occupancy, last_bit_result_median))
                    if abs(median_occupancy - self.n_injections_gdac / 2) > abs(last_bit_result_median - self.n_injections_gdac / 2):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                        self.set_gdac_bit(gdac_bit, bit_value=1)
                        logging.info('Set bit 0 = 1')
                        self.occ_array_sel_pixel = last_bit_result
                        median_occupancy = np.ma.median(self.occ_array_sel_pixel)
                    else:
                        logging.info('Set bit 0 = 0')
                    if abs(occupancy_best - self.n_injections_gdac / 2) < abs(median_occupancy - self.n_injections_gdac / 2):
                        logging.info("Binary search converged to non optimal value, take best measured value instead")
                        median_occupancy = occupancy_best
                        self.register.set_global_register_value("Vthin_AltFine", vthin_af_best)
                        self.register.set_global_register_value("Vthin_AltCoarse", vthin_ac_best)

        if (self.register.get_global_register_value("Vthin_AltFine") == 0 and self.register.get_global_register_value("Vthin_AltCoarse") == 0) or self.register.get_global_register_value("Vthin_AltFine") == 254:
            logging.warning('GDAC reached minimum/maximum value')

        if abs(median_occupancy - self.n_injections_gdac / 2) > 2 * self.max_delta_threshold:
            logging.warning('Global threshold tuning failed. Delta threshold = %f > %f. Vthin_AltCoarse / Vthin_AltFine = %d / %d' % (abs(median_occupancy - self.n_injections_gdac / 2), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
        else:
            logging.info('Tuned GDAC to Vthin_AltCoarse / Vthin_AltFine = %d / %d' % (self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))

        self.vthin_altfine_best = self.register.get_global_register_value("Vthin_AltFine")
        self.vthin_altcoarse_best = self.register.get_global_register_value("Vthin_AltCoarse")

    def analyze(self):
        self.register.set_global_register_value("Vthin_AltFine", self.vthin_altfine_best)
        self.register.set_global_register_value("Vthin_AltCoarse", self.vthin_altcoarse_best)

        plotThreeWay(self.occ_array_sel_pixel.transpose(), title="Occupancy after GDAC tuning (GDAC " + str(self.scan_parameters.GDAC) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_gdac_bit(self, bit_position, bit_value=1):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        if(bit_position < 8):
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine") | (1 << bit_position))
            else:
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine") & ~(1 << bit_position))
        else:
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse") | (1 << (bit_position - 8)))
            else:
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse") & ~(1 << bit_position))
        commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine", "Vthin_AltCoarse"]))
        self.register_utils.send_commands(commands)

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=True, clear_buffer=True, callback=None, errback=self.handle_err)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(GdacTuning)
