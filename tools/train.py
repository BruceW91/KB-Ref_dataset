import torch
from torch.utils.data import DataLoader
from torch.autograd import Variable
from torchvision import transforms
from mn import Basenet
from data import data
from PIL import Image
from tensorboardX import SummaryWriter
import json
import torch.nn.functional as F
from matplotlib import pyplot as plt 
import time
import pdb
import numpy as np
import torch.nn.functional as F
import argparse


argparser = argparse.ArgumentParser()
argparser.add_argument('--vocab_size', type=int, default=15733)
argparser.add_argument('--cand_len', type=int, default=10)
argparser.add_argument('--fact_len', type=int, default=50)
argparser.add_argument('--text_len', type=int, default=50)
argparser.add_argument('--max_episodic', type=int, default=5)
argparser.add_argument('--q_lstm_dim', type=int, default=2048)
argparser.add_argument('--s_lstm_dim', type=int, default=2048)
argparser.add_argument('--o_dim', type=int, default=512)
argparser.add_argument('--l_dim', type=int, default=128)
argparser.add_argument('--g1_dim', type=int, default=512)
args = argparser.parse_args()



def train(epoch, model, critertion, f_loss, optimizer, use_gpu):
    model.train()
    correct = 0
    train_loss = 0
    for batch_id, (jpg, label, f_label, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, path, c_mask) in enumerate(trainDataloader):
        if use_gpu:
            jpg = Variable(jpg.cuda())
            label = Variable(label.cuda())
            f_label = Variable(f_label.cuda())
            expression = Variable(expression.cuda())
            e_mask = Variable(e_mask.cuda())
            locals = Variable(locals.cuda())
            locations = Variable(locations.cuda())
            facts = Variable(facts.cuda())
            mask = Variable(mask.cuda())
            f_mask = Variable(f_mask.cuda())
            ff_mask = Variable(ff_mask.cuda())
            c_mask = Variable(c_mask.cuda())
        else:
            jpg, label = Variable(jpg), Variable(label)
            f_label = Variable(f_label)
            expression = Variable(expression)
            e_mask = Variable(e_mask)
            locals = Variable(locals)
            locations = Variable(locations)
            facts = Variable(facts)
            mask = Variable(mask)
            f_mask = Variable(f_mask)
            ff_mask = Variable(ff_mask)
            c_mask = Variable(c_mask)
        if len(label.size()) == 2:
            label = label.squeeze(1)
        optimizer.zero_grad()
        output = model(jpg, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, c_mask)
        #output, i_weight = model(jpg, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, c_mask)
        #print(3, time.time()-start)
        #print(output.size(), label.size())
        loss = critertion(output, label)
        #print(label)
        #print(f_weight)
        #print(output)
        train_loss += loss.item()
        writer.add_scalar('train_loss', loss.item(), (epoch-1)*len(trainDataloader)+batch_id)
        pred = output.data.max(1)[1]
        correct += pred.eq(label.data).cpu().sum()
        #print(correct)
        loss.backward()
        #pdb.set_trace()
        optimizer.step()
        if batch_id % 20 == 0:
            print('Train Epoch:{} [{}/{} ({:.0f}%)]\tLoss:{:.6f}'.format(
                epoch, batch_id * len(jpg), len(trainDataloader.dataset),
                100. * batch_id / len(trainDataloader), loss.item()
            ))
    train_loss /= len(trainDataloader)
    writer.add_scalar('train_acc', correct / len(trainDataloader.dataset), epoch)
    print('\nTrain Set: Average loss:{:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
        train_loss, correct, len(trainDataloader.dataset),
        100. * correct / len(trainDataloader.dataset)
    ))


def test(epoch, model, critertion, f_loss, use_gpu, Dataset):
    model.eval()
    val_loss = 0
    correct = 0
    result = []
    with torch.no_grad():
        for batch_id, (jpg, label, f_label, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, path, c_mask) in enumerate(Dataset):
            if use_gpu:
                jpg = Variable(jpg.cuda())
                label = Variable(label.cuda())
                f_label = Variable(f_label.cuda())
                expression = Variable(expression.cuda())
                e_mask = Variable(e_mask.cuda())
                locals = Variable(locals.cuda())
                locations = Variable(locations.cuda())
                facts = Variable(facts.cuda())
                mask = Variable(mask.cuda())
                f_mask = Variable(f_mask.cuda())
                ff_mask = Variable(ff_mask.cuda())
                c_mask = Variable(c_mask.cuda())
            else:
                jpg, label = Variable(jpg), Variable(label)
                f_label = Variable(f_label)
                expression = Variable(expression)
                e_mask = Variable(e_mask)
                locals = Variable(locals)
                locations = Variable(locations)
                facts = Variable(facts)
                mask = Variable(mask)
                f_mask = Variable(f_mask)
                ff_mask = Variable(ff_mask)
                c_mask = Variable(c_mask)
            if len(label.size()) == 2:
                label = label.squeeze(1)
            output = model(jpg, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, c_mask)
            #print(label)
            #output, i_weight = model(jpg, expression, e_mask, locals, locations, facts, mask, f_mask, ff_mask, c_mask)
            #print(output.size(), label.size())
            loss = critertion(output, label) #+ f_loss(f_weight, f_label)
            val_loss += loss.item()
            writer.add_scalar('val_loss', loss.item(), (epoch/5-1)*len(Dataset)+batch_id)
            pred = output.data.max(1)[1]
            correct += pred.eq(label.data).cpu().sum()
            #result.append({'image': path,'gt': label.data.cpu().numpy().tolist(),'pred': output.data.cpu().numpy().tolist(),'f_weight': f_weight.detach().cpu().numpy().tolist()})
            result.append({'image': path,'gt': label.data.cpu().numpy().tolist(),'pred': output.data.cpu().numpy().tolist()})
            
        with open('result_mn.json', 'w') as file:
            json.dump(result, file)
        #'''
        val_loss /= len(Dataset)
        writer.add_scalar('val_acc', correct / len(Dataset.dataset), epoch)
        print('\nTest Set: Average loss:{:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.format(
            val_loss, correct, len(Dataset.dataset),
            100. * correct / len(Dataset.dataset)
        ))
        return val_loss


if __name__ == '__main__':
    writer = SummaryWriter('{}/{}'.format('runs', 'mn'))
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    test_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    net = Basenet(args)
    trainDataset = data('../image','../json/train.json', data_transform=train_transform)
    valDataset = data('../image', '../json/val.json', data_transform=test_transform)
    testDataset = data('../image','../json/test.json', data_transform=test_transform)
    trainDataloader = DataLoader(trainDataset, batch_size=16, shuffle=True, num_workers=4, drop_last=True)
    valDataloader = DataLoader(valDataset, batch_size=16, shuffle=True, num_workers=4, drop_last=True)
    testDataloader = DataLoader(testDataset, batch_size=16, shuffle=True, num_workers=4, drop_last=True)
    critertion = torch.nn.CrossEntropyLoss()
    f_loss = torch.nn.BCELoss()
    use_gpu = torch.cuda.is_available()
    no_params = list(map(id, net.f_global.parameters()))
    base_params = filter(lambda x: id(x) not in no_params, net.parameters())
    optimizer = torch.optim.SGD([
        {'params': base_params},
        {'params': net.f_global.parameters(), 'lr': 0}
    ], lr=1e-4, momentum=0.9, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', factor=0.5, patience=1)
    use_gpu = torch.cuda.is_available()
    
    if use_gpu:
        net.cuda()
        net = torch.nn.DataParallel(net)
    for epoch in range(1, 41):
        train(epoch, net, critertion, f_loss, optimizer, use_gpu)
        val_loss = test(epoch, net, critertion, f_loss, use_gpu, valDataloader)
        scheduler.step(val_loss)
        if epoch % 10 == 0:
            torch.save(net, './train'+str(epoch)+'_mn.pth')
            test_loss = test(epoch, net, critertion, f_loss, use_gpu, testDataloader)
    #'''
