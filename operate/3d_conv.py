'''
多通道卷积不同的通道上的卷积核的参数是不同的，而3D卷积则由于卷积核本身是3D的，所以这个由于“深度”造成的看似不同通道上用的就是同一个卷积，权重共享嘛。
总之，多了一个深度通道，这个深度可能是视频上的连续帧，也可能是立体图像中的不同切片
'''