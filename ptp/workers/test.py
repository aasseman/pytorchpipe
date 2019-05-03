
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

import time


# Parameters and DataLoaders
input_size = 5
output_size = 2

batch_size = 30
data_size = 100
from ptp.data_types.data_dict import DataDict

from torch.nn.parallel._functions import Scatter, Gather

from torch.nn.parallel.replicate import replicate
from torch.nn.parallel.parallel_apply import parallel_apply
from torch.nn.parallel.scatter_gather import gather

def datadict_scatter(inputs, target_gpus, dim=0):
    r"""
    Slices tensors into approximately equal chunks and
    distributes them across given GPUs. Duplicates
    references to objects that are not tensors.
    """
    def scatter_map(obj):
        print("scatter_map for {}".format(type(obj).__name__))
        if isinstance(obj, torch.Tensor):
            return Scatter.apply(target_gpus, None, dim, obj)
        if isinstance(obj, tuple) and len(obj) > 0:
            return list(zip(*map(scatter_map, obj)))
        if isinstance(obj, list) and len(obj) > 0:
            return list(map(list, zip(*map(scatter_map, obj))))
        if isinstance(obj, dict) and len(obj) > 0:
            print("LIST!\n")
            return list(map(type(obj), zip(*map(scatter_map, obj.items()))))
        if isinstance(obj, DataDict) and len(obj) > 0:
            print("DataDict!\n")
            aaa = list(map(type(obj), zip(*map(scatter_map, obj.items()))))    
            print("aaa = ",aaa)
            return aaa
        print("ELSE!!!")
        return [obj for targets in target_gpus]

    # After scatter_map is called, a scatter_map cell will exist. This cell
    # has a reference to the actual function scatter_map, which has references
    # to a closure that has a reference to the scatter_map cell (because the
    # fn is recursive). To avoid this reference cycle, we set the function to
    # None, clearing the cell
    try:
        return scatter_map(inputs)
    finally:
        scatter_map = None


def datadict_scatter_kwargs(inputs, kwargs, target_gpus, dim=0):
    r"""Scatter with support for kwargs dictionary"""
    inputs = datadict_scatter(inputs, target_gpus, dim) if inputs else []
    kwargs = datadict_scatter(kwargs, target_gpus, dim) if kwargs else []
    if len(inputs) < len(kwargs):
        inputs.extend([() for _ in range(len(kwargs) - len(inputs))])
    elif len(kwargs) < len(inputs):
        kwargs.extend([{} for _ in range(len(inputs) - len(kwargs))])
    inputs = tuple(inputs)
    kwargs = tuple(kwargs)
    return inputs, kwargs

def datadict_gather(outputs, target_device, dim=0):
    r"""
    Gathers tensors from different GPUs on a specified device
      (-1 means the CPU).
    """
    def gather_map(outputs):
        out = outputs[0]
        if isinstance(out, torch.Tensor):
            return Gather.apply(target_device, dim, *outputs)
        if out is None:
            return None

        if isinstance(obj, DataDict) and len(obj) > 0:
            print("DataDict!\n")
            if not all((len(out) == len(d) for d in outputs)):
                raise ValueError('All dicts must have the same number of keys')
            return type(out)(((k, gather_map([d[k] for d in outputs]))
                              for k in out))

        if isinstance(out, dict):
            if not all((len(out) == len(d) for d in outputs)):
                raise ValueError('All dicts must have the same number of keys')
            return type(out)(((k, gather_map([d[k] for d in outputs]))
                              for k in out))

        return type(out)(map(gather_map, zip(*outputs)))

    # Recursive function calls like this create reference cycles.
    # Setting the function to None clears the refcycle.
    try:
        return gather_map(outputs)
    finally:
        gather_map = None




from itertools import chain


class PTPDataParallel(torch.nn.DataParallel):
    def __init__(self, module, device_ids=None, output_device=None, dim=0):
        super(PTPDataParallel, self).__init__(module, device_ids, output_device, dim)

    # PyTorch v1.0.1
    def forward(self, *inputs, **kwargs):
        # Simple processing.
        if not self.device_ids:
            return self.module(*inputs, **kwargs)
        # One device - also easy.
        if len(self.device_ids) == 1:
            return self.module(*inputs[0], **kwargs[0])

        #print(type(self.module))
        # Preprocessing for scattering: get only the inputs to the model, as list.
        #inputs_tuple = ()
        #for item in inputs:
        #    print(item["index"])
        #    input_dict = {key: value for key,value in item.items() if key in self.module.input_data_definitions().keys()}
        #    inputs_tuple = inputs_tuple + (input_dict,)
        #print("inputs_tuple:",inputs_tuple)

        inputs, kwargs = self.scatter(inputs, kwargs, self.device_ids)
        print("input after scatter():",inputs)

        replicas = self.replicate(self.module, self.device_ids[:len(inputs)])

        self.parallel_apply(replicas, inputs, kwargs)
        print("inputs after parallel_appy(): ",inputs)

        outputs = self.gather(inputs, self.output_device)
        print("after gather(): ",outputs)
        # Return 0-th tuple, i.e. DdataDict.
        return outputs[0]


    def replicate(self, module, device_ids):
        print("REPLICATE\n")
        return replicate(module, device_ids)

    def scatter(self, inputs, kwargs, device_ids):
        print("SCATTER\n")
        return datadict_scatter_kwargs(inputs, kwargs, device_ids, dim=self.dim)

    def parallel_apply(self, replicas, inputs, kwargs):
        print("APPLY\n")
        return parallel_apply(replicas, inputs, kwargs, self.device_ids[:len(replicas)])

    def gather(self, outputs, output_device):
        print("GATHER\n")
        return gather(outputs, output_device, dim=self.dim)


from ptp.components.problems.problem import Problem

class RandomDataset(Problem):

    def __init__(self, size, length):
        self.len = length
        self.data = torch.randn(length, size)

    def __getitem__(self, index):

        # Return data_dict.
        data_dict = DataDict({"index": None})
        data_dict["index"] = self.data[index]

        return data_dict

        #return self.data[index]

    def __len__(self):
        return self.len

    def output_data_definitions(self):
        return {"index": DataDefinition(1,1,"str")}

    #def collate_fn(self, batch):
    #    print("Collate!")
    #    
    #    return DataDict({key: torch.utils.data.dataloader.default_collate([sample[key] for sample in batch]) for key in batch[0]})

from ptp.components.models.model import Model
from ptp.data_types.data_definition import DataDefinition

class TestModel(Model):
    # Our model
    def __init__(self, input_size, output_size):
        super(Model, self).__init__()
        self.fc = nn.Linear(input_size, output_size)

    def forward(self, datadict):
        input = datadict["index"]
        print("Dummy Model: input size {}, device: {}\n".format(input.size(), input.device))
        output = self.fc(input)
        print("Dummy Model: output size {}\n".format(output.size()))

        datadict["output"] = output
        #print("saved to output : ",type(output))
        #return output

    def input_data_definitions(self):
        return {"index": DataDefinition(1,1,"str")}

    def output_data_definitions(self):
        return {"output": DataDefinition(1,1,"str")}




if __name__ == "__main__":
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


    model = TestModel(input_size, output_size)
    print("Model DONE!!")
    #time.sleep(2)

    dataset = RandomDataset(input_size, data_size)
    rand_loader = DataLoader(dataset=dataset, batch_size=batch_size, shuffle=True)#, collate_fn=dataset.collate_fn)
    print("Dataloader DONE!!")
    #time.sleep(2)


    if torch.cuda.device_count() > 1:
        print("Let's use", torch.cuda.device_count(), "GPUs!")
        # dim = 0 [30, xxx] -> [10, ...], [10, ...], [10, ...] on 3 GPUs
        model = PTPDataParallel(model)        
    model.to(device)
    print("DataParallel DONE!!")
    #time.sleep(2)

    #datadict1 = {}#DataDict({"index":None,"output":None})
    for datadict in rand_loader:
        print("Got object from loader: {}".format(type(datadict)))
        #datadict = DataDict(datadict)
        #new_datadict = DataDict({key: None for key in datadict.keys()})
        #new_datadict["index"] = datadict["index"].to(self.device)
        #datadict = new_datadict
        print("Before to device: ", type(datadict["index"]),datadict["index"].device)
        
        datadict["index"] = datadict["index"].to(device)
        print("After to device: ", type(datadict["index"]),datadict["index"].device)
        #print(datadict)

        #data=datadict["index"]

        #print("For: before to: input data ({}) size {}, device: {}\n".format(type(data), data.size(), data.device))
        #data = data.to(self.device)
        #datadict.to(self.device)
        #print("For: before model: input data ({}) size {}, device: {}\n".format(type(data), data.size(), data.device))
        print("datadict before model: ",datadict)
        outputs = model(datadict)
        for key in model.module.output_data_definitions().keys():
            datadict[key] = outputs[key]

        print("datadict after model: ",datadict)
        
        #output = datadict["output"]
        #print(type(output))
        #output = datadict2["output"]
        #print("For: after model: output_size ", output.size(),"\n")

