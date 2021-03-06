"""
Session hardware object.

Contains information regarding the current session and methods to
access and manipulate this information.
"""
import os
import time

from HardwareRepository.BaseHardwareObjects import HardwareObject

__author__ = "Marcus Oskarsson"
__copyright__ = "Copyright 2012, ESRF"
__credits__ = ["My great coleagues", "The MxCuBE colaboration"]

__version__ = "0.1"
__maintainer__ = "Marcus Oskarsson"
__email__ = "marcus.oscarsson@esrf.fr"
__status__ = "Beta"


class Session(HardwareObject):
    def __init__(self, name):
        HardwareObject.__init__(self, name)
        self.session_id = None
        self.proposal_code = None
        self.proposal_number = None
        self.proposal_id = None
        self.in_house_users = []
        self.endstation_name = None

        self.default_precision = '04'
        self.suffix = None
        self.base_directory = None
        self.base_process_directory = None
        self.raw_data_folder_name = None
        self.processed_data_folder_name = None

    # Framework-2 method, inherited from HardwareObject and called
    # by the framework after the object has been initialized.
    def init(self):
        self.endstation_name = self.getProperty('endstation_name').lower()
        self.suffix = self["file_info"].getProperty('file_suffix')
        self.base_directory = self["file_info"].\
                              getProperty('base_directory')

        self.base_process_directory = self["file_info"].\
            getProperty('processed_data_base_directory')

        self.raw_data_folder_name = self["file_info"].\
            getProperty('raw_data_folder_name')

        self.processed_data_folder_name = self["file_info"].\
            getProperty('processed_data_folder_name')

        inhouse_proposals = self["inhouse_users"]["proposal"]

        for prop in inhouse_proposals:
            self.in_house_users.append((prop.getProperty('code'),
                str(prop.getProperty('number'))))

    def get_base_data_directory(self):
        """
        Returns the base data directory taking the 'contextual'
        information into account, such as if the current user
        is inhouse.

        :returns: The base data path.
        :rtype: str
        """
        user_category = ''
        directory = ''

        if self.is_inhouse():
            user_category = 'inhouse'
            directory = os.path.join(self.base_directory,
                                     self.endstation_name,
                                     user_category,
                                     self.get_proposal(),
                                     time.strftime("%Y%m%d"))
        else:
            user_category = 'visitor'
            directory = os.path.join(self.base_directory,
                                     user_category,
                                     self.get_proposal(),
                                     self.endstation_name,
                                     time.strftime("%Y%m%d"))

        return directory

    def get_base_image_directory(self):
        """
        :returns: The base path for images.
        :rtype: str
        """
        return os.path.join(self.get_base_data_directory(),
                            self.raw_data_folder_name) + '/'

    def get_base_process_directory(self):
        """
        :returns: The base path for procesed data.
        :rtype: str
        """
        return os.path.join(self.get_base_data_directory(),
                            self.processed_data_folder_name)+ '/'

    def get_image_directory(self, sub_dir):
        """
        Returns the full path to images, using the name of each of
        data_nodes parents as sub directories.

        :param data_node: The data node to get additional
                          information from, (which will be added
                          to the path).
        :type data_node: TaskNode

        :returns: The full path to images.
        :rtype: str
        """
        directory = self.get_base_image_directory()

        if sub_dir:
            sub_dir = sub_dir.replace(' ', '').replace(':', '-')
            directory = os.path.join(directory, sub_dir) + '/'

        return directory

    def get_process_directory(self, sub_dir=None):
        """
        Returns the full path to processed data, using the name of
        each of data_nodes parents as sub directories.

        :param data_node: The data node to get additional
                          information from, (which will be added
                          to the path).
        :type data_node: TaskNode

        :returns: The full path to images.
        """
        directory = self.get_base_process_directory()

        if sub_dir:
            sub_dir = sub_dir.replace(' ', '').replace(':', '-')
            directory = os.path.join(directory, sub_dir) + '/'

        return directory

    def get_default_prefix(self, sample_data_node = None, generic_name = False):
        """
        Returns the default prefix, using sample data such as the
        acronym as parts in the prefix.

        :param sample_data_node: The data node to get additional
                                 information from, (which will be
                                 added to the prefix).
        :type sample_data_node: Sample


        :returns: The default prefix.
        :rtype: str
        """
        proposal = self.get_proposal()
        prefix = proposal

        if sample_data_node:
            if sample_data_node.has_lims_data():
                prefix = sample_data_node.crystals[0].protein_acronym + \
                         '-' + sample_data_node.name
        elif generic_name:
            prefix = '<acronym>-<name>'

        return prefix

    def get_proposal(self):
        """
        :returns: The proposal, 'local-user' if no proposal is
                  available
        :rtype: str
        """
        proposal = 'local-user'

        if self.proposal_code and self.proposal_number:
            if self.proposal_code == 'ifx':
                self.proposal_code = 'fx'

            proposal = "%s%s" % (self.proposal_code,
                                 self.proposal_number)

        return proposal

    def is_inhouse(self, proposal_code=None, proposal_number=None):
        """
        Determines if a given proposal is considered to be inhouse.

        :param proposal_code: Proposal code
        :type propsal_code: str

        :param proposal_number: Proposal number
        :type proposal_number: str

        :returns: True if the proposal is inhouse, otherwise False.
        :rtype: bool
        """
        if not proposal_code:
            proposal_code = self.proposal_code

        if not proposal_number:
            proposal_number = self.proposal_number

        if (proposal_code, proposal_number) in self.in_house_users:
            return True
        else:
            return False

    def get_inhouse_user(self):
        """
        :returns: The current inhouse user.
        :rtype: tuple (<proposal_code>, <proposal_number>)
        """
        return self.in_house_users[0]
