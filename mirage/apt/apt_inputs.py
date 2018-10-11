# ! /usr/bin/env python

'''
Given APT output files, read in data relevant to the data simulator,
organize, and create input files for the simulator.

Inputs:

xml file - Name of xml file exported from APT.
pointing file - Name of associated pointing file exported from APT.

Optional inputs:

epoch_list - Name of ascii file which lists observation labels and
             associated starting observation time, as well as telescope
             roll angle (PAV3). If you wish to have observations back-
             to-back, give them all the same starting time.

Outputs:

output_csv - Ascii table containing all relevant information needed
             to construct a ramp simulator input file for each
             observation/dither/detector combination.

Dependencies:

argparse, lxml, astropy, numpy, collections

JWST Calibration pipeline (only for the use of set_telescope_pointing.py)
in order to translate PAV3 values to local roll angles for each detector.

rotations.py - Colin Cox's module of WCS-related functions


HISTORY:

July 2017 - V0: Initial version. Bryan Hilbert
Feb 2018  - V1: Updated to work for multiple filter pairs per observation
            Lauren Chambers
August 2018 - V2: Replaced manual Ra, Dec calculations with pysiaf functionality
'''
import copy
import os
import re
import argparse

from astropy.table import Table, vstack
from astropy.io import ascii
import numpy as np
from pysiaf import rotations
import yaml

from . import read_apt_xml
from ..utils import rotations
from ..utils import siaf_interface


class AptInput:
    """Summary

    Attributes:
        exposure_tab (TYPE): Description
        input_xml (str): Description
        observation_table (str): Description
        obstab (TYPE): Description
        output_csv (TYPE): Description
        pointing_file (str): Description
    """

    def __init__(self):
        self.input_xml = ''  # e.g. 'GOODSS_ditheredDatasetTest.xml'
        self.output_csv = None  # e.g. 'GOODSS_ditheredDatasetTest.csv'
        self.pointing_file = ''  #  e.g. 'GOODSS_ditheredDatasetTest.pointing'
        self.observation_table = ''

    def add_epochs(self, intab):
        """NOT CURRENTLY USED"""
        # add information on the epoch of each observation
        # if the user entered a list of epochs, read that in
        default_date = '2020-10-14'

        if self.epoch_list is not None:
            epochs = ascii.read(self.epoch_list, header_start=0, data_start=1)
        else:
            epochs = Table()
            epochs['observation'] = intab['obs_label']
            epochs['date'] = ['2018-10-14'] * len(intab['obs_label'])
            epochs['pav3'] = [0.] * len(intab['obs_label'])

        # insert epoch info for each observation into dictionary
        epoch_start = []
        epoch_pav3 = []
        for obs in intab['obs_label']:
            match = obs == epochs['observation'].data
            if np.sum(match) == 0:
                print("No valid epoch line found for observation {}".format(obs))
                print(epochs['observation'].data)
                epoch_start.append(default_date)
                epoch_pav3.append(0.)
            else:
                epoch_start.append(epochs['date'][match].data[0])
                epoch_pav3.append(epochs['pav3'][match].data[0])
        intab['epoch_start_date'] = epoch_start
        intab['pav3'] = epoch_pav3
        return intab

    def add_observation_info(self, intab):
        """
        Add information about each observation. Catalog names,
        dates, PAV3 values, etc., which are retrieved from the
        observation list yaml file.

        Parameters
        ----------
        intab : obj
            astropy.table.Table containing exposure information

        Returns
        -------
        intab : obj
            Updated table with information from the observation list
            yaml file added.
        """

        with open(self.observation_table, 'r') as infile:
            self.obstab = yaml.load(infile)

        onames = []
        onums = []
        for observation in self.obstab:
            onames.append(self.obstab[observation]['Name'])
            onums.append(observation)
        onames = np.array(onames)

        OBSERVATION_LIST_FIELDS = 'Name Date PAV3 Filter PointSourceCatalog GalaxyCatalog ExtendedCatalog ExtendedScale ExtendedCenter MovingTargetList MovingTargetSersic MovingTargetExtended MovingTargetConvolveExtended MovingTargetToTrack BackgroundRate'.split()

        unique_instrument_names = [name.lower() for name in np.unique(intab['Instrument'])]

        obs_start = []
        if len(unique_instrument_names) == 1: # only one instrument
            if unique_instrument_names[0] == 'nircam':


                obs_pav3 = []
                obs_sw_ptsrc = []
                obs_sw_galcat = []
                obs_sw_ext = []
                obs_sw_extscl = []
                obs_sw_extcent = []
                obs_sw_movptsrc = []
                obs_sw_movgal = []
                obs_sw_movext = []
                obs_sw_movconv = []
                obs_sw_solarsys = []
                obs_sw_bkgd = []
                obs_lw_ptsrc = []
                obs_lw_galcat = []
                obs_lw_ext = []
                obs_lw_extscl = []
                obs_lw_extcent = []
                obs_lw_movptsrc = []
                obs_lw_movgal = []
                obs_lw_movext = []
                obs_lw_movconv = []
                obs_lw_solarsys = []
                obs_lw_bkgd = []

                # This will allow the filter values
                # in the observation table to override
                # what comes from APT. This is useful for
                # WFSS observations, where you want to create
                # 'direct images' in various filters to hand
                # to the disperser software in order to create
                # simulated dispersed data. In that case, you
                # would need to create 'direct images' using
                # several filters inside the filter listed in APT
                # in order to get broadband colors to disperse.
                # If filter names are present in the observation
                # yaml file, then they will be used. If not, the
                # filters from APT will be kept
                obs_sw_filt = []
                obs_lw_filt = []

                for exp, obs in zip(intab['exposure'], intab['obs_label']):
                    match = np.where(obs == onames)[0]
                    if len(match) == 0:
                        raise ValueError("No valid epoch line found for observation {} in observation table ({}).".format(obs, onames))

                    # Match observation from observation table yaml file with observatoins
                    # from  APT XML/pointing; extract the date and PAV3
                    obslist = self.obstab[onums[match[0]]]
                    obs_start.append(obslist['Date'].strftime('%Y-%m-%d'))
                    obs_pav3.append(obslist['PAV3'])

                    # Determine if this is a newly-generated yaml that
                    # include separate FilterConfig# keys
                    obstab_keys = self.obstab['Observation1'].keys()
                    filter_configs = any(['FilterConfig' in k for k in  obstab_keys])
                    if filter_configs:
                        # If so, match up with the filter configuration using
                        # the exposure number
                        exposure = int(exp[-2:])
                        filter_config = 'FilterConfig{}'.format(exposure)
                        obslist = obslist[filter_config]

                    # Read parameters from yaml
                    obs_sw_ptsrc.append(self.full_path(obslist['SW']['PointSourceCatalog']))
                    obs_sw_galcat.append(self.full_path(obslist['SW']['GalaxyCatalog']))
                    obs_sw_ext.append(self.full_path(obslist['SW']['ExtendedCatalog']))
                    obs_sw_extscl.append(obslist['SW']['ExtendedScale'])
                    obs_sw_extcent.append(obslist['SW']['ExtendedCenter'])
                    obs_sw_movptsrc.append(self.full_path(obslist['SW']['MovingTargetList']))
                    obs_sw_movgal.append(self.full_path(obslist['SW']['MovingTargetSersic']))
                    obs_sw_movext.append(self.full_path(obslist['SW']['MovingTargetExtended']))
                    obs_sw_movconv.append(obslist['SW']['MovingTargetConvolveExtended'])
                    obs_sw_solarsys.append(self.full_path(obslist['SW']['MovingTargetToTrack']))
                    obs_sw_bkgd.append(obslist['SW']['BackgroundRate'])
                    obs_lw_ptsrc.append(self.full_path(obslist['LW']['PointSourceCatalog']))
                    obs_lw_galcat.append(self.full_path(obslist['LW']['GalaxyCatalog']))
                    obs_lw_ext.append(self.full_path(obslist['LW']['ExtendedCatalog']))
                    obs_lw_extscl.append(obslist['LW']['ExtendedScale'])
                    obs_lw_extcent.append(obslist['LW']['ExtendedCenter'])
                    obs_lw_movptsrc.append(self.full_path(obslist['LW']['MovingTargetList']))
                    obs_lw_movgal.append(self.full_path(obslist['LW']['MovingTargetSersic']))
                    obs_lw_movext.append(self.full_path(obslist['LW']['MovingTargetExtended']))
                    obs_lw_movconv.append(obslist['LW']['MovingTargetConvolveExtended'])
                    obs_lw_solarsys.append(self.full_path(obslist['LW']['MovingTargetToTrack']))
                    obs_lw_bkgd.append(obslist['LW']['BackgroundRate'])

                    # Override filters if given
                    try:
                        obs_sw_filt.append(obslist['SW']['Filter'])
                    except:
                        pass
                    try:
                        obs_lw_filt.append(obslist['LW']['Filter'])
                    except:
                        pass

                # intab['epoch_start_date'] = obs_start
                intab['pav3'] = obs_pav3
                intab['sw_ptsrc'] = obs_sw_ptsrc
                intab['sw_galcat'] = obs_sw_galcat
                intab['sw_ext'] = obs_sw_ext
                intab['sw_extscl'] = obs_sw_extscl
                intab['sw_extcent'] = obs_sw_extcent
                intab['sw_movptsrc'] = obs_sw_movptsrc
                intab['sw_movgal'] = obs_sw_movgal
                intab['sw_movext'] = obs_sw_movext
                intab['sw_movconv'] = obs_sw_movconv
                intab['sw_solarsys'] = obs_sw_solarsys
                intab['sw_bkgd'] = obs_sw_bkgd
                intab['lw_ptsrc'] = obs_lw_ptsrc
                intab['lw_galcat'] = obs_lw_galcat
                intab['lw_ext'] = obs_lw_ext
                intab['lw_extscl'] = obs_lw_extscl
                intab['lw_extcent'] = obs_lw_extcent
                intab['lw_movptsrc'] = obs_lw_movptsrc
                intab['lw_movgal'] = obs_lw_movgal
                intab['lw_movext'] = obs_lw_movext
                intab['lw_movconv'] = obs_lw_movconv
                intab['lw_solarsys'] = obs_lw_solarsys
                intab['lw_bkgd'] = obs_lw_bkgd

                # Here we override the filters read from APT
                # if they are given in the observation yaml file
                if len(obs_sw_filt) > 0:
                    intab['ShortFilter'] = obs_sw_filt
                if len(obs_lw_filt) > 0:
                    intab['LongFilter'] = obs_lw_filt

            # NIRISS case
            elif unique_instrument_names[0] == 'niriss':
                for key in OBSERVATION_LIST_FIELDS:
                    intab[key] = []

                for exp, obs in zip(intab['exposure'], intab['obs_label']):
                    match = np.where(obs == onames)[0]
                    if len(match) == 0:
                        raise ValueError("No valid epoch line found for observation {} in observation table ({}).".format(obs, onames))

                    # Match observation from observation table yaml file with observatoins
                    # from  APT XML/pointing; extract the date and PAV3
                    obslist = self.obstab[onums[match[0]]]
                    obs_start.append(obslist['Date'].strftime('%Y-%m-%d'))
                    for key in OBSERVATION_LIST_FIELDS:
                        if key == 'Date':
                            value = obslist[key].strftime('%Y-%m-%d')
                        else:
                            value = str(obslist[key])

                        intab[key].append(value)

                # intab['epoch_start_date'] = obs_start

        else:
            if ('fgs' in unique_instrument_names and 'niriss' in unique_instrument_names) | ('miri' in unique_instrument_names and 'niriss' in unique_instrument_names) | ('nirspec' in unique_instrument_names and 'niriss' in unique_instrument_names):
            # if unique_instrument_names[0] == 'niriss':
                for key in OBSERVATION_LIST_FIELDS:
                    intab[key] = []

                for exp, obs in zip(intab['exposure'], intab['obs_label']):
                    match = np.where(obs == onames)[0]
                    if len(match) == 0:
                        raise ValueError(
                            "No valid epoch line found for observation {} in observation table ({"
                            "}).".format(
                                obs, onames))

                    # Match observation from observation table yaml file with observatoins
                    # from  APT XML/pointing; extract the date and PAV3
                    obslist = self.obstab[onums[match[0]]]
                    obs_start.append(obslist['Date'].strftime('%Y-%m-%d'))
                    for key in OBSERVATION_LIST_FIELDS:
                        if key == 'Date':
                            value = obslist[key].strftime('%Y-%m-%d')
                        else:
                            value = str(obslist[key])

                        intab[key].append(value)


                # intab['epoch_start_date'] = obs_start

            else:
                raise NotImplementedError

        intab['epoch_start_date'] = obs_start
        return intab

    def base36encode(self, integer):
        """
        Translate a base 10 integer to base 36

        Parameters
        ----------
        integer : int
            a base 10 integer

        Returns
        -------
        integer : int
            The integer translated to base 36
        """
        chars, encoded = '0123456789abcdefghijklmnopqrstuvwxyz', ''

        while integer > 0:
            integer, remainder = divmod(integer, 36)
            encoded = chars[remainder] + encoded

        return encoded.zfill(2)

    def combine_dicts(self, dict1, dict2):
        """
        Combine two dictionaries into a single dictionary

        Parameters
        ----------
        dict1 : dict
            dictionary
        dict2 : dict
            dictionary

        Returns
        -------
        combined : dict
            Combined dictionary
        """
        combined = dict1.copy()
        combined.update(dict2)
        return combined

    def create_input_table(self):
        """MAIN FUNCTION"""
        # Expand paths to full paths
        self.input_xml = os.path.abspath(self.input_xml)
        self.pointing_file = os.path.abspath(self.pointing_file)
        if self.output_csv is not None:
            self.output_csv = os.path.abspath(self.output_csv)
        if self.observation_table is not None:
            self.observation_table = os.path.abspath(self.observation_table)

        main_dir = os.path.split(self.input_xml)[0]

        # if APT.xml content has already been generated during observation list creation
        # (write_observationlist.py) load it here
        if self.apt_xml_dict is not None:
            tab = self.apt_xml_dict
        else:
            # Read in xml file
            readxml_obj = read_apt_xml.ReadAPTXML()
            tab = readxml_obj.read_xml(self.input_xml)

        # This affects on NIRCam exposures (right?)
        # If the number of dithers is set to '3TIGHT'
        # (currently only used in NIRCam)
        # remove 'TIGHT' from the entries and leave
        # only the number behind
        tight = [True if 'TIGHT' in str(val) else False for val in tab['PrimaryDithers']]
        if np.any(tight):
            tab = self.tight_dithers(tab)

        # Expand the dictionary for multiple dithers. Expand such that there
        # is one entry in each list for each exposure, rather than one entry
        # for each set of dithers
        if (np.all(np.array(tab['PrimaryDithers']).astype(int) == 1) and np.all(np.array(tab['ImageDithers']).astype(int) == 1)): # NIRCam and NIRISS dither names
            # skip step if no dithers are included
            xmltab = tab
        else:
            xmltab = self.expand_for_dithers(tab)


        # Read in the pointing file and produce dictionary
        pointing_tab = self.get_pointing_info(self.pointing_file, propid=xmltab['ProposalID'][0])
        # pointing_tab = self.get_pointing_info(self.pointing_file)

        # Check that the .xml and .pointing files agree
        assert len(xmltab['ProposalID']) == len(pointing_tab['obs_num']),\
            'Inconsistent table size from XML file ({}) and pointing file ({}). Something was not processed correctly in apt_inputs.'.format(len(xmltab['ProposalID']), len(pointing_tab['obs_num']))


        # Combine the dictionaries
        obstab = self.combine_dicts(xmltab, pointing_tab)

        verbose = False
        if verbose:
            print('Summary of observation dictionary:')
            for key in obstab.keys():
                print('{:<25}: number of elements is {:>5}'.format(key, len(obstab[key])))
            # for key in


        # Add epoch and catalog information
        obstab = self.add_observation_info(obstab)

        # NIRCam case: Expand for detectors. Create one entry in each list for each
        # detector, rather than a single entry for 'ALL' or 'BSALL'

        # test if Module is always 'None', i.e. when NIRCam is not used
        if obstab['Module'].count('None') == len(obstab['Module']):
            # set detector key
            obstab['detector'] = []
            for i, instrument in enumerate(obstab['Instrument']):
                if instrument.lower() == 'niriss':
                    obstab['detector'].append('NIS')
                elif instrument.lower() == 'fgs':
                    if 'FGS1' in obstab['aperture'][i]:
                        obstab['detector'].append('G1')
                    elif 'FGS2' in obstab['aperture'][i]:
                        obstab['detector'].append('G2')
            self.exposure_tab = obstab
        else:
            self.exposure_tab = self.expand_for_detectors(obstab)


        # for key in self.exposure_tab.keys():
        #     print('{:>20} has {:>10} items'.format(key, len(self.exposure_tab[key])))

        detectors_file = os.path.join(self.output_dir, 'expand_for_detectors.csv')
        ascii.write(Table(self.exposure_tab), detectors_file, format='csv', overwrite=True)
        print('Wrote exposure table to {}'.format(detectors_file))

        # Calculate the correct V2, V3 and RA, Dec for each exposure/detector
        self.ra_dec_update()

        # Output to a csv file.
        if self.output_csv is None:
            indir, infile = os.path.split(self.input_xml)
            self.output_csv = os.path.join(self.output_dir, 'Observation_table_for_' + infile + '.csv')
        ascii.write(Table(self.exposure_tab), self.output_csv, format='csv', overwrite=True)
        print('Final csv exposure list written to {}'.format(self.output_csv))

    def expand_for_detectors(self, obstab):
        """
        Expand dictionary to have one entry per detector, rather than the
        one line per module that is in the input

        Parameters
        ----------
        obstab : dict
            dictionary containing one entry per module

        Returns
        -------
        finaltab : dict
            dictionary expanded to have one entry per detector
        """
        finaltab = {}
        for key in obstab:
            finaltab[key] = []
        finaltab['detector'] = []

        n_primarydithers = len(obstab['PrimaryDithers'])
        for i in range(n_primarydithers):
            # Determine module of the observation
            module = obstab['Module'][i]
            if module == 'ALL':
                detectors = ['A1', 'A2', 'A3', 'A4', 'A5', 'B1', 'B2', 'B3', 'B4', 'B5']
            elif module == 'A':
                detectors = ['A1', 'A2', 'A3', 'A4', 'A5']
            elif module == 'B':
                detectors = ['B1', 'B2', 'B3', 'B4', 'B5']
            elif 'A3' in module:
                detectors = ['A3']
            elif 'B4' in module:
                detectors = ['B4']
            elif 'DHSPIL' in module:
                if module[-1] == 'A':
                    detectors = ['A3']
                elif module[-1] == 'B':
                    detectors = ['B4']
                else:
                    ValueError('Unknown module {}'.format(module))
            else:
                raise ValueError('Unknown module {}'.format(module))

            n_detectors = len(detectors)
            for key in obstab:
                finaltab[key].extend(([obstab[key][i]] * n_detectors))
            finaltab['detector'].extend(detectors)

        return finaltab

    def expand_for_dithers(self, indict):
        """Expand a given dictionary to create one entry
        for each dither
        define the dictionary to hold the expanded entries

        In here we should also reset the primary and subpixel dither
        numbers to 1, to avoid confusion.

        Parameters
        ----------
        indict :dict
            dictionary of observations

        Returns
        -------
        expanded : dict
            Dictionary, expanded to include a separate entry for
            each dither
        """
        expanded = {}
        for key in indict:
            expanded[key] = []

        # Loop over entries in dict and duplicate by the
        # number of dither positions
        # keys = np.array(indict.keys())
        keys = indict.keys()
        if not np.all(np.array(indict['PrimaryDithers']).astype(int) == 1):
            # NIRCam exposures
            for i in range(len(indict['PrimaryDithers'])):
                arr = np.array([item[i] for item in indict.values()])
                entry = dict(zip(keys, arr))

                # In WFSS, SubpixelPositions will be either '4-Point' or '9-Point'
                subpix = entry['SubpixelPositions']
                if subpix in ['0', 'NONE']:
                    subpix = [[1]]
                if subpix == '4-Point':
                    subpix = [[4]]
                if subpix == '9-Point':
                    subpix = [[9]]

                primary = entry['PrimaryDithers']
                if primary == '0':
                    primary = [1]
                reps = np.int(subpix[0][0]) * np.int(primary[0])
                for key in keys:
                    for j in range(reps):
                        expanded[key].append(indict[key][i])

        if not np.all(np.array(indict['ImageDithers']).astype(int) == 1):
            # use astropy table operations to expand dithers while maintaining parallels in sync
            # implementation assumes that only one instrument is used in parallel

            table = Table(indict)
            table['row'] = np.arange(len(table))
            expanded_table = None #copy.deepcopy(table)

            for i, row in enumerate(table['row']):
                if (table['CoordinatedParallel'][i] == 'true') and (not table['ParallelInstrument'][i]):
                    dither_table = table[i:i + 2]

                    if (table['ImageDithers'][i] > 1):
                        #replicate parallel observation n times
                        dither_table = vstack([dither_table]*(table['ImageDithers'][i]))

                    if expanded_table is None:
                        expanded_table = dither_table
                    else:
                        expanded_table = vstack((expanded_table, dither_table))
                elif (table['CoordinatedParallel'][i] == 'false'):
                    # add row multiplied by number of dithers
                    dither_table = vstack([table[i]]*table['ImageDithers'][i])
                    if expanded_table is None:
                        expanded_table = dither_table
                    else:
                        expanded_table = vstack((expanded_table, dither_table))


            # expanded_table['Instrument', 'ImageDithers', 'ParallelInstrument'].pprint()
            expanded = {}
            for key in expanded_table.colnames:
                expanded[key] = np.array(expanded_table[key]).tolist()
            # expanded = dict(expanded_table)

            # for i in range(len(indict['ImageDithers'])):
            #     arr = np.array([item[i] for item in indict.values()])
            #     entry = dict(zip(keys, arr))
            #
            #     primary = entry['ImageDithers']
            #     # if primary == '0':
            #     #     primary = [1]
            #     reps = np.int(primary)
            #     for key in keys:
            #         for j in range(reps):
            #             expanded[key].append(indict[key][i])

        return expanded

    def extract_value(self, line):
        """Extract text from xml line

        Parameters
        ----------
        line : str
            Line from xml file

        Returns
        -------
        line : str
            Text between > and < in the input line
        """
        gt = line.find('>')
        lt = line.find('<', gt)
        return line[gt + 1:lt]

    def full_path(self, in_path):
        """
        If the input path is not None, expand
        any environment variables and make an
        absolute path. Return the updated path.

        Parameters
        ----------
        in_path : str
            Path to be expanded

        Returns
        -------
        in_path : str
            Expanded, absolute path
        """
        if in_path.lower() == 'none':
            return in_path
        else:
            return os.path.abspath(os.path.expandvars(in_path))

    def get_pointing_info(self, file, propid=0, verbose=True):
        """Read in information from APT's pointing file.

        Parameters
        ----------
        file : str
            Name of APT-exported pointing file to be read
        propid : int
            Proposal ID number (integer). This is used to
            create various ID fields

        Returns:
        --------
        pointing : dict
            Dictionary of pointing-related information
        """
        tar = []
        tile = []
        exp = []
        dith = []
        aperture = []
        targ1 = []
        targ2 = []
        ra = []
        dec = []
        basex = []
        basey = []
        dithx = []
        dithy = []
        v2 = []
        v3 = []
        idlx = []
        idly = []
        level = []
        type_str = []
        expar = []
        dkpar = []
        ddist = []
        observation_number = []
        visit_number = []
        visit_id = []
        visit_grp = []
        activity_id = []
        observation_label = []
        observation_id = []
        seq_id = []

        act_counter = 1
        with open(file) as f:
            for line in f:

                #skip comments and new lines
                if (line[0] == '#') or (line in ['\n']) or ('=====' in line):
                    continue
                # extract proposal ID
                elif line.split()[0] == 'JWST':
                    propid_header = line.split()[7]
                    try:
                        propid = np.int(propid_header)
                    except ValueError:
                        #adopt value passed to function
                        pass
                    if verbose:
                        print('Extracted proposal ID {}'.format(propid))
                    continue

                # TODO: extract useful information from header?
                elif (len(line) > 1):
                    elements = line.split()

                    # Look for lines that give visit/observation numbers
                    if line[0:2] == '* ':
                        paren = line.rfind('(')
                        if paren == -1:
                            obslabel = line[2:]
                            obslabel = obslabel.strip()
                        else:
                            obslabel = line[2:paren-1]
                            obslabel = obslabel.strip()
                        if (' (' in obslabel) and (')' in obslabel):
                            obslabel = re.split(r' \(|\)', obslabel)[0]

                        # if 'FGS' in obslabel:
                        #     skip = True
                        # else:
                        #     skip = False
                        skip = False

                    if line[0:2] == '**':
                        v = elements[2]
                        obsnum, visitnum = v.split(':')
                        obsnum = str(obsnum).zfill(3)
                        visitnum = str(visitnum).zfill(3)
                        if skip is True:
                            print('Skipping observation {} ({})'.format(obsnum, obslabel))

                    try:
                    # if 1:
                        # Skip the line at the beginning of each
                        # visit that gives info on the target,
                        # but is not actually an observation
                        # These lines have 'Exp' values of 0,
                        # while observations have a value of 1
                        # (that I've seen so far)
                        #
                        # Also, skip non-NIRCam lines. Check for NRC in aperture name
                        # Add NIRISS and FGS support (JSA)
                        if ((np.int(elements[1]) > 0) & ('NRC' in elements[4]
                                                         or 'NIS' in elements[4]
                                                         or 'FGS' in elements[4]
                                                         or 'NRS' in elements[4]
                                                         or 'MIR' in elements[4])
                            ):
                            if skip:
                                act_counter += 1
                                continue
                            act = self.base36encode(act_counter)
                            activity_id.append(act)
                            observation_label.append(obslabel)
                            observation_number.append(obsnum)
                            visit_number.append(visitnum)
                            prop_5digit = "{0:05d}".format(int(propid))
                            vid = "{}{}{}".format(prop_5digit, obsnum, visitnum)
                            visit_id.append(vid)
                            # Visit group hard coded to 1. It's not clear how APT divides visits up into visit
                            # groups. For now just keep everything in a single visit group.
                            vgrp = '01'
                            visit_grp.append(vgrp)
                            # Parallel sequence id hard coded to 1 (Simulated instrument as prime rather than
                            # parallel) at the moment. Future improvements may allow the proper sequence
                            # number to be constructed.
                            seq = '1'
                            seq_id.append(seq)
                            tar.append(np.int(elements[0]))
                            tile.append(np.int(elements[1]))
                            exnum = str(elements[2]).zfill(5)
                            exp.append(exnum)
                            dith.append(np.int(elements[3]))

                            ap = elements[4]
                            if ('GRISMR_WFSS' in elements[4]):
                                ap = ap.replace('GRISMR_WFSS', 'FULL')
                            elif ('GRISMC_WFSS' in elements[4]):
                                ap = ap.replace('GRISMC_WFSS', 'FULL')

                            aperture.append(ap)
                            targ1.append(np.int(elements[5]))
                            targ2.append(elements[6])
                            ra.append(elements[7])
                            dec.append(elements[8])
                            basex.append(elements[9])
                            basey.append(elements[10])
                            dithx.append(np.float(elements[11]))
                            dithy.append(np.float(elements[12]))
                            v2.append(np.float(elements[13]))
                            v3.append(np.float(elements[14]))
                            idlx.append(np.float(elements[15]))
                            idly.append(np.float(elements[16]))
                            level.append(elements[17])
                            type_str.append(elements[18])
                            expar.append(np.int(elements[19]))
                            dkpar.append(np.int(elements[20]))
                            if elements[18] == 'PARALLEL':
                                ddist.append(None)
                            else:
                                ddist.append(np.float(elements[21]))
                            # 1/0
                            # For the moment we assume that the instrument being simulated is not being
                            # run in parallel, so the parallel proposal number will be all zeros,
                            # as seen in the line below.
                            observation_id.append("V{}P{}{}{}{}".format(vid, '00000000', vgrp, seq, act))
                            act_counter += 1

                    except ValueError as e:
                        print('Skipping line:\n{}\nproducing error:\n{}'.format(line, e))
                        pass

        pointing = {'exposure': exp, 'dither': dith, 'aperture': aperture,
                    'targ1': targ1, 'targ2': targ2, 'ra': ra, 'dec': dec,
                    'basex': basex, 'basey': basey, 'dithx': dithx,
                    'dithy': dithy, 'v2': v2, 'v3': v3, 'idlx': idlx,
                    'idly': idly, 'obs_label': observation_label,
                    'obs_num': observation_number, 'visit_num': visit_number,
                    'act_id': activity_id, 'visit_id': visit_id, 'visit_group': visit_grp,
                    'sequence_id': seq_id, 'observation_id': observation_id}
        return pointing

    def tight_dithers(self, input_dict):
        """
        In NIRCam, when the 'FULL' dither pattern is
        used, it is possible to set the number of primary
        dithers to '3TIGHT' rather than just a number
        (e.g. '3'). If the number of dithers is set to '3TIGHT'
        remove 'TIGHT' from the entries and leave
        only the number behind.

        Parameters
        ----------

        input_dict : dict
           Dictionary where each key points to a list containing
           observation details. For example, input_dict['PrimarDither']
           is a list of the number of primary dithers for all observations

        Returns
        -------

        input_dict : dict
            Updated dictionary where 'TIGHT' has been removed from
            PrimaryDither list
        """
        inlist = input_dict['PrimaryDithers']
        modlist = [v if 'TIGHT' not in v else v.strip('TIGHT') for v in inlist]
        input_dict['PrimaryDithers'] = modlist
        return input_dict

    def ra_dec_update(self):
        """Given the V2, V3 values for the reference pixels associated
        with detector apertures, calculate corresponding RA, Dec.
        """
        aperture_ra = []
        aperture_dec = []


        # 1/0
        for i in range(len(self.exposure_tab['Module'])):
            siaf_instrument = self.exposure_tab["Instrument"][i]
            aperture_name = self.exposure_tab['aperture'][i]
            # print('{} {}'.format(siaf_instrument, aperture_name))
            pointing_ra = np.float(self.exposure_tab['ra'][i])
            pointing_dec = np.float(self.exposure_tab['dec'][i])
            pointing_v2 = np.float(self.exposure_tab['v2'][i])
            pointing_v3 = np.float(self.exposure_tab['v3'][i])

            if 'pav3' in self.exposure_tab.keys():
                pav3 = np.float(self.exposure_tab['pav3'][i])
            else:
                pav3 = np.float(self.exposure_tab['PAV3'][i])

            telescope_roll = pav3

            aperture, local_roll, attitude_matrix, fullframesize, subarray_boundaries = \
                siaf_interface.get_siaf_information(
                siaf_instrument, aperture_name, pointing_ra, pointing_dec, telescope_roll,
                    v2_arcsec=pointing_v2, v3_arcsec=pointing_v3)

            # calculate RA, Dec of reference location for the detector
            ra, dec = rotations.pointing(attitude_matrix, aperture.V2Ref, aperture.V3Ref)
            aperture_ra.append(ra)
            aperture_dec.append(dec)

        # # 1/0
        #
        #
        #
        #
        # if siaf_instrument == 'NIRCAM':
        #     siaf_instrument = "NIRCam"
        #
        #
        # scripts_path = os.path.dirname(os.path.realpath(__file__))
        # modpath = os.path.split(scripts_path)[0]
        # for i in range(len(self.exposure_tab['Module'])):
        #
        #     # First find detector
        #     # need ra, dec and v2, v3 pairs from entry
        #     # to calculate ra, dec at each detector's reference location
        #     if self.exposure_tab['Instrument'][i].lower() == 'nircam':
        #         subarray_def_file = os.path.join(modpath, 'config', 'NIRCam_subarray_definitions.list')
        #         detector = 'NRC' + self.exposure_tab['detector'][i]
        #         sub = self.exposure_tab['Subarray'][i]
        #         aperture = detector + '_' + sub
        #     elif self.exposure_tab['Instrument'][i].lower() == 'niriss':
        #         subarray_def_file = os.path.join(modpath, 'config', 'niriss_subarrays.list')
        #         aperture = self.exposure_tab['aperture'][i]
        #     else:
        #         raise ValueError('Incompatible instrument: ' + self.exposure_tab['Instrument'][i])
        #
        #     config = ascii.read(subarray_def_file)
        #     if aperture in config['AperName']:
        #         pass
        #     else:
        #         aperture = [
        #             apername for apername, name in np.array(config['AperName', 'Name']) if
        #             (sub in apername) or (sub in name)
        #         ]
        #         if len(aperture) > 1 or len(aperture) == 0:
        #             raise ValueError('Cannot combine detector {} and subarray {}\
        #                 into valid aperture name.'.format(detector, sub))
        #         else:
        #             aperture = aperture[0]
        #
        #     pointing_ra = np.float(self.exposure_tab['ra'][i])
        #     pointing_dec = np.float(self.exposure_tab['dec'][i])
        #     pointing_v2 = np.float(self.exposure_tab['v2'][i])
        #     pointing_v3 = np.float(self.exposure_tab['v3'][i])
        #
        #     if 'pav3' in self.exposure_tab.keys():
        #         pav3 = np.float(self.exposure_tab['pav3'][i])
        #     else:
        #         pav3 = np.float(self.exposure_tab['PAV3'][i])
        #
        #     # calculate local roll angle
        #     local_roll = set_telescope_pointing.compute_local_roll(pav3, pointing_ra,
        #                                                            pointing_dec,
        #                                                            pointing_v2,
        #                                                            pointing_v3)
        #     # create attitude_matrix
        #     attitude_matrix = rotations.attitude(pointing_v2, pointing_v3,
        #                                          pointing_ra, pointing_dec, local_roll)
        #
        #     # find v2, v3 of the reference location for the detector
        #     siaf_object = pysiaf.Siaf(siaf_instrument)[aperture]
        #     aperture_v2 = siaf_object.V2Ref
        #     aperture_v3 = siaf_object.V3Ref
        #     # aperture_v2, aperture_v3 = self.ref_location(distortionTable, aperture)
        #
        #     # calculate RA, Dec of reference location for the detector
        #     ra, dec = rotations.pointing(attitude_matrix, aperture_v2, aperture_v3)
        #     aperture_ra.append(ra)
        #     aperture_dec.append(dec)
        self.exposure_tab['ra_ref'] = aperture_ra
        self.exposure_tab['dec_ref'] = aperture_dec

    def add_options(self, parser=None, usage=None):
        if parser is None:
            parser = argparse.ArgumentParser(usage=usage, description='Simulate JWST ramp')
        parser.add_argument("input_xml", help='XML file from APT describing the observations.')
        parser.add_argument("pointing_file", help='Pointing file from APT describing observations.')
        parser.add_argument("--output_csv", help="Name of output CSV file containing list of observations.", default=None)
        parser.add_argument("--observation_table", help='Ascii file containing a list of observations, times, and roll angles, catalogs', default=None)
        return parser


if __name__ == '__main__':

    usagestring = 'USAGE: apt_inputs.py NIRCam_obs.xml NIRCam_obs.pointing'

    input = AptInput()
    parser = input.add_options(usage=usagestring)
    args = parser.parse_args(namespace=input)
    input.create_input_table()
