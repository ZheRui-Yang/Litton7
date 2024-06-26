import argparse
import os
import shutil
import sys
import time
import platform
import traceback

import pandas as pd
import torch
import torch.nn.functional as F
import gdown

from PIL import Image
from torch.autograd import Variable
from torchvision import transforms


class PrintHelpBeforeLeaveArgumentParser(argparse.ArgumentParser):
    "An argument parser with helpful error message."

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
            print("-" * 75)
        if status:
            self.print_help()
        sys.exit(status)

    def error(self, message):
        args = {"prog": self.prog, "message": message}
        self.exit(2, ("%(prog)s: error: %(message)s\n") % args)


desc = """\
Categorize images and save the results to the specified output folder.
Then, transfer the image files into new sub-folders named after
Litton's 7 class categories.
"""
epilog = """\
The program is a batch process.
Given a folder with image files in its sub-folders:

root-folder
├── sub-folder1
│   ├── 00001.jpg
│   ├── 00002.jpg
│   ├── 00003.jpg
│   ...
├── sub-folder2
│   ├── 00004.jpg
│   ├── 00005.jpg
│   ├── 00006.jpg
│   ...
└── sub-folder3
    ├── 00007.jpg
    ├── 00008.jpg
    ├── 00009.jpg
    ...

Set the path of the "root-folder" for this program, and it will process 
the first level of sub-folders sequentially.

Please ensure that the "root-folder" contains only sub-folders.
"""


parser = PrintHelpBeforeLeaveArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=desc,
    epilog=epilog,
)
parser.add_argument("rootfolder", help="Path to the directory to be processed")
parser.add_argument("-m", "--model", help="Specify the model explicitly")
parser.add_argument(
    "-o",
    "--output",
    default="output",
    help="Folder for the output CSV (default: ./output)",
)
parser.add_argument(
    "-d",
    "--device",
    help=(
        "Use CPU or which GPU. (default: auto) "
        "`auto` to automatically choose device, "
        "`cpu` for pure CPU, "
        "0, 1, 2, ... to specify which GPU device. "
    ),
    default="auto",
)

args = parser.parse_args()

if args.model is None:
    if not os.path.exists("Litton-7type-visual-landscape-model.pth"):
        gdown.download(
            id="1177rxfD7Yx5F5ZzEqDGBeAIYHTLU3lj9",
            output="Litton-7type-visual-landscape-model.pth",
        )
    args.model = "Litton-7type-visual-landscape-model.pth"
else:
    if not os.path.exists(args.model):
        print(
            f"the model you have specifyed, {args.model}, do not exists",
            file=sys.stderr,
        )
        sys.exit(1)
    if not os.path.isfile(args.model):
        print(
            f"the model you have specifyed, {args.model}, is not a file.",
            file=sys.stderr,
        )
        sys.exit(1)

if args.device.lower() == "auto":
    if platform.system() == "Darwin":
        args.device = "mps" if torch.backends.mps.is_available() else "cpu"
    else:
        args.device = "cuda:0" if torch.cuda.is_available() else "cpu"
elif args.device.lower() == "cpu":
    args.device = "cpu"
else:
    if not args.device.isdigit():
        print(
            "--device must be one of 'cpu', 'auto', or an integer number.",
            file=sys.stderr,
        )
        sys.exit(1)

    if platform.system() == "Darwin":
        print(
            "MacOS (MPS backend) do not support specify GPU by index", file=sys.stderr
        )
        sys.exit(1)

    args.device = f"cuda:{args.device}"

os.makedirs(args.output, exist_ok=True)


labels = [
    "0.Panoramic-landscape",
    "1.Feature-landscape",
    "2.Detail-landscape",
    "3.Enclosed-landscape",
    "4.Focal-landscape",
    "5.Ephemeral-landscape",
    "6.Canopied-landscape",
]


labelsnum = []
for i in range(len(labels)):
    labelsnum.append(str(i))
img_type = [".jpg", ".bmp", ".png"]

try:
    model = torch.load(args.model).to(args.device).eval()
except Exception as exc:
    print(
        (
            f"Could not load model, `{args.model}`. Abort.\n"
            f"For details, please check `.{os.sep}error.log`."
        ),
        file=sys.stderr,
    )
    with open("error.log", "w") as ferr:
        traceback.print_exception(exc, file=ferr)
    sys.exit(2)

normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
preprocess = transforms.Compose(
    [
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        normalize,
    ]
)


def main(imgpath):
    imgname = []
    imglabel = []
    imglabelnum = []
    rate = []
    error = []
    bset_out = number = checknumber = i = 0
    check = num = point = 0

    print("total " + str(len(os.listdir(imgpath))) + " images")
    imagepath_list = os.listdir(imgpath)
    imagepath_list.sort()
    for infile in imagepath_list:
        try:
            for i in range(len(labels)):
                if infile == labels[i]:
                    continue
                fpath = os.path.join(imgpath, labels[i])
                if not os.path.isdir(fpath):
                    os.mkdir(fpath)
            for check in img_type:
                if infile.find(check) == -1:
                    continue
            name = os.path.join(imgpath, infile)
            img_pil = Image.open(name).convert("RGB")
            img_tensor = preprocess(img_pil).to(args.device)
            img_tensor = img_tensor.unsqueeze_(0)
            fc_out = model(Variable(img_tensor))
            fc_out = F.softmax(fc_out, dim=1)
            fc_out.tolist()

        except:
            print("error: " + name)
            error.append(name)

        else:
            transfer_list = []
            for out in fc_out:
                for x in range(len(labelsnum)):
                    transfer_list.append(fc_out[0][x].item())
            best_out = max(transfer_list)
            i = transfer_list.index(best_out)
            label = labels[i]
            labelnum = labelsnum[i]
            rate.append(best_out)
            imgname.append(infile)
            imglabel.append(label)
            imglabelnum.append(labelnum)
            newpath = os.path.join(imgpath, label, infile)
            shutil.move(name, newpath)
    dict = {
        "imgname": imgname,
        "predict_label": imglabel,
        "predict_label_num": imglabelnum,
        "probability": rate,
    }
    df = pd.DataFrame(dict)
    df.to_csv(csv_path, encoding="utf_8_sig", index=False)
    if error:
        dict = {"error_imgname": error}
        df = pd.DataFrame(dict)
        df.to_csv(error_csv_path, encoding="utf_8_sig", index=False)
        print("error: " + error_csv_path + " has been created!")
        error = []


os.makedirs(args.output, exist_ok=True)

folderpath_list = os.listdir(args.rootfolder)
folderpath_list.sort()
for f in folderpath_list:
    start = time.time()
    imgpath = os.path.join(args.rootfolder, f)

    csv_path = os.path.join(
        args.output, f + "-Litton-7type-visual-landscape-predict_result.csv"
    )
    error_csv_path = os.path.join(args.output, f + "-predict_error.csv")
    print(csv_path)
    main(imgpath)
    end = time.time()
    print("Costing " + str(end - start) + " sec")
    print("---------------------------------------------------------------------")
print("done")
