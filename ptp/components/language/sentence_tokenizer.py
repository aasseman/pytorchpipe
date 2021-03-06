# Copyright (C) tkornuta, IBM Corporation 2019
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = "Tomasz Kornuta"

import nltk
#from nltk.tokenize import WhitespaceTokenizer
import string

from ptp.components.component import Component
from ptp.data_types.data_definition import DataDefinition

from ptp.configuration.config_parsing import get_value_list_from_dictionary


class SentenceTokenizer(Component):
    """
    Class responsible for tokenizing the sentence.
    """
    def __init__(self, name, config):
        """
        Initializes the component.

        :param name: Component name (read from configuration file).
        :type name: str

        :param config: Dictionary of parameters (read from the configuration ``.yaml`` file).
        :type config: :py:class:`ptp.configuration.ConfigInterface`

        """
        # Call constructors of parent classes.
        Component.__init__(self, name, SentenceTokenizer, config)

        # Read the actual configuration.
        self.mode_detokenize = config['detokenize']

        # Get preprocessing.
        self.preprocessing = get_value_list_from_dictionary(
            "preprocessing", self.config,
            'none | lowercase | remove_punctuation | all'.split(" | ")
            )
        if 'none' in self.preprocessing:
            self.preprocessing = []
        if 'all' in self.preprocessing:
            self.preprocessing = 'lowercase | remove_punctuation'.split(" | ")
        self.logger.info("Applied preprocessing: {}".format(self.preprocessing))

        self.remove_characters = get_value_list_from_dictionary("remove_characters", self.config)
        self.logger.info("Additional characters that will be removed during preprocessing: {}".format(self.remove_characters))

        if 'remove_punctuation' in self.preprocessing:
            self.translator = str.maketrans('', '', string.punctuation)

        # Tokenizer.
        self.tokenizer = nltk.tokenize.WhitespaceTokenizer()

        # Set key mappings.
        self.key_inputs = self.stream_keys["inputs"]
        self.key_outputs = self.stream_keys["outputs"]

        if self.mode_detokenize:
            # list of strings -> sentence.
            self.processor = self.detokenize_sample
        else:
            # sentence -> list of strings.
            self.processor = self.tokenize_sample
        # Ok, we are ready to go!


    def input_data_definitions(self):
        """ 
        Function returns a dictionary with definitions of input data that are required by the component.

        :return: dictionary containing input data definitions (each of type :py:class:`ptp.utils.DataDefinition`).
        """
        if self.mode_detokenize == False:
            return { self.key_inputs: DataDefinition([-1, 1], [list, str], "Batch of sentences, each represented as a single string [BATCH_SIZE] x [string]") }
        else:
            return { self.key_inputs: DataDefinition([-1, -1, 1], [list, list, str], "Batch of tokenized sentences, each represented as a list of words [BATCH_SIZE] x [SEQ_LENGTH] x [string]") }


    def output_data_definitions(self):
        """ 
        Function returns a dictionary with definitions of output data produced the component.

        :return: dictionary containing output data definitions (each of type :py:class:`ptp.utils.DataDefinition`).
        """
        if self.mode_detokenize == False:
            return { self.key_outputs: DataDefinition([-1, -1, 1], [list, list, str], "Batch of tokenized sentences, each represented as a list of words [BATCH_SIZE] x [SEQ_LENGTH] x [string]") }
        else:
            return { self.key_outputs: DataDefinition([-1, 1], [list, str], "Batch of sentences, each represented as a single string [BATCH_SIZE] x [string]") }


    def tokenize_sample(self, text):
        """
        Changes text (sentence) into list of tokens (words).

        :param text: sentence (string).

        :return: list of words (strings).
        """
        # Lowercase.
        if 'lowercase' in self.preprocessing:
            text = text.lower()

        # Remove characters.
        for char in self.remove_characters:
            text = text.replace(char, ' ')

        # Remove punctuation.
        if 'remove_punctuation' in self.preprocessing:
            text = text.translate(self.translator)

        # Tokenize.
        text_words = self.tokenizer.tokenize(text)

        return text_words

    def detokenize_sample(self, sample):
        """
        Changes list of tokens (words) into sentence.

        :param sample: list of words (strings).

        :return: sentence (string).
        """
        return ' '.join([str(x) for x in sample])

    def __call__(self, data_streams):
        """
        Encodes batch, or, in fact, only one field of bach ("inputs").
        Stores result in "encoded_inputs" field of in data_streams.

        :param data_streams: :py:class:`ptp.utils.DataStreams` object containing (among others):

            - "inputs": expected input field containing list of words

            - "encoded_targets": added field containing output, tensor with encoded samples [BATCH_SIZE x 1] 
        """
        # Get inputs to be encoded.
        inputs = data_streams[self.key_inputs]
        outputs_list = []
        # Process samples 1 by one.
        for sample in inputs:
            output = self.processor(sample)
            # Add to outputs.
            outputs_list.append( output )
        # Create the returned dict.
        data_streams.publish({self.key_outputs: outputs_list})
