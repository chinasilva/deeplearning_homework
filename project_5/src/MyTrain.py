﻿import torch
import torch.nn as nn
import numpy as np
from torch.utils import data
import os
from datetime import datetime
from MyNet import PNet,RNet,ONet
from MyData import MyData
from utils import deviceFun,writeTag
from MyEnum import MyEnum
import multiprocessing

class MyTrain():
    def __init__(self,Net,epoch,batchSize,imgPath,tagPath,testTagPath,testImgPath,testResult):
        multiprocessing.set_start_method('spawn', True)
        '''
        Net:PNet,RNet,ONet对应需要训练的网络名称
        epoch,batchSize 批次和轮次
        '''
        self.netName=Net
        self.testResult=testResult
        self.device=deviceFun()
        self.fileLoction= str('/mnt/D/code/deeplearning_homework/project_5/model/'+self.netName+'.pth')
        if Net=='PNet':
            self.net=PNet().to(self.device)
        elif Net=='RNet':
            self.net=RNet().to(self.device)
        elif Net=='ONet':
            self.net=ONet().to(self.device)
        else:
            raise RuntimeError('训练时,请输入正确的网络名称')
        self.batchSize=batchSize
        self.epoch=epoch
        self.myData=MyData(tagPath,imgPath)
        self.testData=MyData(testTagPath,testImgPath)
        # self.lossFun1=nn.BCEWithLogitsLoss()
        self.lossFun1=nn.BCELoss()
        self.lossFun2=nn.MSELoss()
        if os.path.exists(self.fileLoction):
            self.net=torch.load(self.fileLoction)
        self.optimizer=torch.optim.Adam(self.net.parameters())
        
    def train(self):
        trainData=data.DataLoader(self.myData,batch_size=self.batchSize,shuffle=True,drop_last=True,num_workers=0)
        testData=data.DataLoader(self.testData,batch_size=self.batchSize,shuffle=True)
        # trainData=data.DataLoader(self.myData,batch_size=self.batchSize,shuffle=False,drop_last=True)
        losslst=[]
        for i in range(self.epoch):
            print("epoch:",i)
            try:
                for j,(img,offset) in enumerate(trainData):
                    #训练分为两种损失
                    #1.negative与positive
                    #2.positive与part
                    # offset=confidence,offsetX1,offsetY1,offsetX2,offsetY2
                    a=datetime.now()
                    outputClass,outputBox,outputLandMark=self.net(img.to(self.device))
                    index=offset[:,0]!=MyEnum.part.value # 过滤部分人脸样本，进行比较
                    target1=offset[index] 
                    target1=target1[:,:1] #取第0位,置信度
                    output1=outputClass[index].reshape(-1,1)
                    output1=output1[:,:1] #取第0位,置信度
                    loss1=self.lossFun1(output1.to(self.device),target1.to(self.device))

                    index2=offset[:,0]!=MyEnum.negative.value # 过滤非人脸样本，进行比较
                    target2=offset[index2] 
                    target2=target2[:,1:5] #取第1-4位,偏移量
                    output2=outputBox[index2].reshape(-1,4)
                    output2=output2[:,:5]
                    loss2=self.lossFun2(target2.to(self.device),output2.to(self.device))
                    
                    loss=loss1+loss2

                    self.optimizer.zero_grad()
                    loss.backward()
                    self.optimizer.step()
                
                    
                    
                    b=datetime.now()
                    c=(b-a).microseconds//1000
                    print("epoch:{},batch:{}, loss1:{},loss2:{},loss:{},用时{}ms".format(i,j,loss1.data,loss2.data,loss.data,c))
                    torch.save(self.net,self.fileLoction)
                    
                    if j%10==0:  #每10批次打印loss
                        with torch.no_grad():
                            self.net.eval()
                            correct = 0.
                            error = 0.
                            total = 0.
                            for _,(input, target) in enumerate(testData):
                                input, target = input.to(self.device), target.to(self.device)
                                output,outputBox,outputLandMark = self.net(input)
                                predicted=output[:,0,0,0] #输出的2个值
                                target=target[:,0]
                                # _, predicted = torch.max(output.data, 1)
                                total += target.size(0)
                                predicted=torch.where(predicted<0.1,torch.zeros_like(predicted),predicted)
                                predicted=torch.where(predicted>0.9,torch.ones_like(predicted),predicted)
                                correct += (predicted == target).sum()
                                error += (predicted != target).sum()
                                accuracy = correct.float() / total
                                recall = correct.float() / correct+error

                            print("[epochs - {0}]Accuracy:{1}%".format(i + 1, (100 * accuracy)))
                            tagLst=[self.netName,i + 1,(100 * accuracy),(100 *recall),0]
                            writeTag(self.testResult,tagLst)
            except Exception as e:
                print("train",str(e))
  
if __name__ == "__main__":
    
    imgPath=r'/mnt/D/code/deeplearning_homework/project_5/test/48/positive'
    tagPath=r'/mnt/D/code/deeplearning_homework/project_5/test/48'
    testTagPath=r''
    testImgPath=r''
    myTrain=MyTrain(Net='ONet',epoch=1,batchSize=2,imgPath=imgPath,tagPath=tagPath,testTagPath=testTagPath,testImgPath=testTagPath)
    myTrain.train()

    
