from MyTrain import MyTrain


if __name__ == "__main__":
    path=r"./pic2"
    epoch=100
    batchSize=64
    myTrain=MyTrain(path,epoch,batchSize)
    myTrain.train()