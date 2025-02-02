﻿import torch
import torch.nn as nn
import numpy as np
from torch.utils import data
import os
from datetime import datetime
from MyNet import PNet,RNet,ONet,CenterLoss
from MyData import MyData
from utils import deviceFun,writeTag,iou,iouSpecial
from MyEnum import MyEnum
import multiprocessing
import matplotlib.pyplot as plt
from MyArcLoss import ArcMarginProduct 
from Lookahead import Lookahead
from torch.utils.tensorboard import SummaryWriter

class MyTrain():
    def __init__(self,Net,epoch,batchSize,imgPath,tagPath,testTagPath,testImgPath,testResult):
        # multiprocessing.set_start_method('spawn', True)
        '''
        Net:PNet,RNet,ONet对应需要训练的网络名称
        epoch,batchSize 批次和轮次
        '''
        self.writer = SummaryWriter(log_dir="./runs/{}_runs".format(Net))
        self.netName=Net
        self.testResult=testResult
        self.device=deviceFun()
        self.modelPath= str('/home/chinasilva/code/deeplearning_homework/project_5/model/'+self.netName+'.pth')
        if Net=='PNet':
            self.centlossSize=32
            self.size=12
            self.net=PNet().to(self.device)
        elif Net=='RNet':
            self.centlossSize=128
            self.size=24
            self.net=RNet().to(self.device)
        elif Net=='ONet':
            self.centlossSize=256
            self.size=48
            self.net=ONet().to(self.device)
        else:
            raise RuntimeError('训练时,请输入正确的网络名称')
        self.batchSize=batchSize
        self.epoch=epoch
        self.myData=MyData(tagPath,imgPath)
        self.testData=MyData(testTagPath,testImgPath)
        self.lossFun1=nn.MSELoss()#reduction='none'
        self.lossFun2=nn.MSELoss()#reduction='none'
        self.lossFun3=nn.MSELoss()#reduction='none'
        # self.lossFun1=nn.BCELoss()
        # self.lossFun2=nn.MSELoss()
        # self.lossFun3=nn.MSELoss()
        self.criterion=nn.CrossEntropyLoss()
        self.center_loss_layer = CenterLoss(2, self.centlossSize)

        if os.path.exists(self.modelPath):
            self.net=torch.load(self.modelPath)

        # self.optimizer=torch.optim.SGD(self.net.parameters(), lr=0.001,momentum=0.9,weight_decay=0.00003)
        # self.optimizer3 = torch.optim.SGD(self.net.parameters(),lr=0.5)
        # self.optimizer3 = torch.optim.Adam(self.center_loss_layer.parameters())

        # self.optimizer=torch.optim.Adam(self.net.parameters())
        self.optimizer=torch.optim.SGD(self.net.parameters(), lr=0.0001,momentum=0.9,weight_decay=0.0005)
        self.optimizer2 = Lookahead(self.optimizer, k=5, alpha=0.5) # Initialize Lookahead


        
    def train(self):
        trainData=data.DataLoader(self.myData,batch_size=self.batchSize,shuffle=True,num_workers=4) #,drop_last=True
        testData=data.DataLoader(self.testData,batch_size=512,shuffle=True,num_workers=4)#
        losslst=[]
        # retLayer=ArcMarginProduct(32,2)
        testlosses=[]
        trainLosses=[]
        accumulation_steps = 32
        for i in range(self.epoch):
            
            # print("epoch:",i)
            try:
                for j,(img,offset,imgName) in enumerate(trainData):
                    #训练分为两种损失
                    #1.negative与positive
                    #2.positive与part
                    # offset=confidence,offsetX1,offsetY1,offsetX2,offsetY2
                    a=datetime.now()
                    outputClass,outputBox,outputLandMark,iouValue,centerLoss=self.net(img.to(self.device))
                    # self.writer.add_histogram("Weight1",self.net.PNet[0].weight.data,global_step=i)
                    # self.writer.add_histogram("Weight2",self.net.PNet[3].weight.data,global_step=i)
                    # self.writer.add_histogram("Weight3",self.net.PNet[5].weight.data,global_step=i)


                    index=offset[:,0]!=MyEnum.part.value # 过滤部分人脸样本，进行比较
                    target1=offset[index] 
                    target1=target1[:,:1] #取第0位,置信度
                    output1=outputClass[index].reshape(-1,1)
                    output1=output1[:,:1] #取第0位,置信度
                    centerLoss=centerLoss[index].reshape(-1,self.centlossSize)#(N,V)


                    loss1=self.lossFun1(output1.to(self.device),target1.to(self.device))

                    loss_center = 0.003*self.center_loss_layer(centerLoss.to(self.device), target1.view(-1).to(self.device))
                    # centerLoss2=retLayer(centerLoss,target1)
                    # loss5=self.criterion(centerLoss2.to(self.device),target1.view(-1).long().to(self.device))

                    # loss1=self.onlineHardSampleMining(loss1,output1,hardRate=0.7)
                    

                    index2=offset[:,0]!=MyEnum.negative.value # 过滤非人脸样本，进行比较
                    target2=offset[index2] 
                    target2=target2[:,1:5] #取第1-4位,偏移量
                    output2=outputBox[index2].reshape(-1,4)
                    output2=output2[:,:5]

                    loss2=self.lossFun2(target2.to(self.device),output2.to(self.device))

                    # loss2=self.onlineHardSampleMining(loss2,output2,hardRate=0.7)
                    output3=iouValue.view(-1,1)
                    target3=self.learnIOU(offset=offset,size=self.size)
                    target3=torch.tensor(target3).view(-1,1)
                    loss3=self.lossFun3(target3.to(self.device),output3.to(self.device))
                    # loss3=self.onlineHardSampleMining(loss3,output3,hardRate=0.7)
                    
                    
                    loss=loss1+0.5*loss2+0.5*loss3#+loss_center #+loss3 0.5*


                    # 2.1 loss regularization
                    # loss = loss/accumulation_steps
                    # 2.2 back propagation
                    # self.optimizer2.zero_grad()   # reset gradient
                    self.optimizer2.zero_grad()   # reset gradient
                    loss.backward()
                    # 3. update parameters of net
                    # if((j+1)%accumulation_steps)==0:
                        # optimizer the net
                    self.optimizer2.step()        # update parameters of net



                    # self.optimizer2.zero_grad()
                    # # self.optimizer3.zero_grad()
                    # loss1.backward()
                    # self.optimizer2.step()


                    # self.optimizer3.step()
                    # if i%100==0:
                    #     print("begin")
                    #     torch.save(self.net,self.modelPath)
                    #     print("epoch:{0},batch:{1}, loss1:{2},loss2:{3},loss_center:{4},loss:{5}".format(i,j,loss1.data,loss2.data,loss_center.data,loss.data))
                    #     print("end")
                    if j%100==0:  #每100批次打印loss
                        b=datetime.now()
                        c=(b-a).microseconds//1000
                        print("epoch:{0},batch:{1}, loss1:{2},loss2:{3},loss3:{4},loss:{5},用时{6}ms".format(i,j,loss1.data,loss2.data,loss3.data,loss.data,c))
                        torch.save(self.net,self.modelPath)
                        print("save,success!!!")
                        tagLst=[]
                        with torch.no_grad():
                            torch.norm
                            testloss=0
                            trainLoss=0.
                            accuracyTrain,recallTrain,trainLoss=self.analysize(trainData)
                            accuracy,recall,testloss=self.analysize(testData)
                            testlosses.append(testloss)
                            trainLosses.append(trainLoss)
                            self.saveModel(accuracy,recall,i,self.netName)
                            
                            tag1=[self.netName,i + 1,(100 * accuracy),(100 *recall),testloss,"Test"]
                            tag2=[self.netName,i + 1,(100 * accuracyTrain),(100 *recallTrain),trainLoss,"Train"]
                            tagLst.append(tag1)
                            tagLst.append(tag2)
                            writeTag(self.testResult,tagLst)
                            self.writer.add_scalar("train Loss",trainLoss,global_step=i)
                            self.writer.add_scalar("test Loss",testloss,global_step=i)
                            # self.draw(i,testlosses,trainLosses)

            # plt.savefig("loss.jpg")
            # plt.ioff() # 画动态图
            # plt.show() # 保留最后一张，程序结束后不关闭
            except Exception as e:
                print("train",str(e))

    def analysize(self,testData):
        correct =0.
        accuracy=0.
        recall=0.
        total = 0.
        TP=0.
        FN=0.
        tureTotal=0.
        loss=0.
        # totalLoss=0.
        for x,(input, target,imgName) in enumerate(testData):
            if x>9:#每次测试选取10*size个样本
                break
            input, myTarget = input.to(self.device), target.to(self.device)
            output,outputBox,outputLandMark,iouValue,centerLoss = self.net(input)
            if self.netName=='PNet':
                predicted=output[:,0,0,0] #输出的2个值
            else:
                predicted=output[:,0] #输出的2个值
            target=myTarget[:,0]
            total += target.size(0)
            target=torch.where(target==2,torch.ones_like(target),target) #测试时目标样本为部分样本时当做正样本看待
            predicted=torch.where(predicted<0.1,torch.zeros_like(predicted),predicted)
            predicted=torch.where(predicted>0.8,torch.ones_like(predicted),predicted)



            index=myTarget[:,0]!=MyEnum.part.value # 过滤部分人脸样本，进行比较
            target1=myTarget[index] 
            target1=target1[:,:1] #取第0位,置信度
            output1=output[index].reshape(-1,1)
            output1=output1[:,:1] #取第0位,置信度
            # totalLoss+=target1[:,0].size(0)

            # loss+=self.lossFun1(output1.to(self.device),target1.to(self.device))
            loss+=torch.mean(self.lossFun1(output1.to(self.device),target1.to(self.device)))

            correct += (predicted == target).sum()
            Positive=torch.where(target==1,torch.ones_like(target),torch.zeros_like(target)) 
            tureTotal+=Positive.sum() #所有正样本总数
            indx= Positive!=0
            TP += (predicted[indx] == Positive[indx]).sum() #正样本预测正确个数
            FN += (predicted != target).sum() #所有样本预测错误中，正样本个数
        recall = TP.float() / (tureTotal+0.000001)
        accuracy = correct.float() / (total+0.000001)
        loss=loss/10
        return accuracy,recall,loss

    def saveModel(self,accuracy,recall,i,netName):
        print("[epochs - {0}]Accuracy:{1}%".format(i + 1, (100 * accuracy)))
        if((accuracy>0.92 and netName=='ONet') or (accuracy>0.85 and netName=='RNet')):
            torch.save(self.net,self.modelPath+str(accuracy.item())+"---"+str(recall.item()))
        if (recall>0.85 and netName=='PNet'):
            torch.save(self.net,self.modelPath+str(accuracy.item())+"---"+str(recall.item()))
        print("save,success!!!")

    def onlineHardSampleMining(self,loss,output,hardRate):
        '''
        困难样本训练
        '''
        outLen=int((output.size()[0]*hardRate))
        loss=loss[:][torch.argsort(loss[:,0],dim=0,descending=True)] #进行困难样本训练
        loss=torch.mean(loss[0:outLen+1])
        return loss

    def learnIOU(self,offset,size):
        offset2=offset[:,1:5] #过滤置信度
        offsetNew=offset2*size #还原到对应比例的位置
        x1=0-offsetNew[:,0]
        y1=0-offsetNew[:,1]
        x2=size-offsetNew[:,2]
        y2=size-offsetNew[:,3]
        boxes=torch.stack((x1,y1,x2,y2),dim=1)
        iouValue=iou((0,0,size,size),boxes.numpy()) #以(0,0,size,size)为右下角坐标
        iouValue=np.where(iouValue==1,0,iouValue) #对负样本iou进行强制为0,因为标签中负样本偏移量默认为0
        return iouValue

    def draw(self,i,losses,losses2):
        '''
        losses:Test
        losses2:Train
        '''
        # losses=list(filter(lambda x: x<0.3,losses)) #过滤部分损失，使图象更直观
        # x=range(len(losses)*(i+1),len(losses)*(i+2))
        # x2=range(len(losses2)*(i+1),len(losses2)*(i+2))

        # plt.subplot(2, 1, 1)
        plt.plot(losses,label = "test",color='cyan')
        plt.plot(losses2,label = "train",color='black')
        plt.ylabel('Test losses')
        plt.savefig(self.netName+"loss.jpg")

        # x2=range(len(losses2)*(i),len(losses2)*(i+1))
        # plt.subplot(2, 1, 2)
        # plt.plot(x2,losses2)
        # plt.pause(0.5)
        # plt.ylabel('Train losses')

        # losses2=[]
        # losses=[]
if __name__ == "__main__":
    
    imgPath=r'/mnt/D/code/deeplearning_homework/project_5/test/48/positive'
    tagPath=r'/mnt/D/code/deeplearning_homework/project_5/test/48'
    testTagPath=r''
    testImgPath=r''
    myTrain=MyTrain(Net='ONet',epoch=1,batchSize=2,imgPath=imgPath,tagPath=tagPath,testTagPath=testTagPath,testImgPath=testTagPath)
    myTrain.train()

    
