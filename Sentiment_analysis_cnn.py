import d2lzh as d2l
from mxnet import gluon, init, nd
from mxnet.contrib import text
from mxnet.gluon import data as gdata, loss as gloss, nn

def corr1d(X, K):
    w = K.shape[0]
    Y = nd.zeros((X.shape[0] - w + 1))
    for i in range(Y.shape[0]):
        Y[i] = (X[i: i + w] * K).sum()
    return Y

X, K = nd.array([0, 1, 2, 3, 4, 5, 6]), nd.array([1, 2])
print(corr1d(X, K))

def corr1d_multi_in(X, K):
    # 首先沿着X和K的第0维（通道维）遍历。然后使用*将结果列表变成add_n函数的位置参数
    #（positional argument）来进行相加
    return nd.add_n(*[corr1d(x, k) for x, k in zip(X, K)])

X = nd.array([[0, 1, 2, 3, 4, 5, 6],
              [1, 2, 3, 4, 5, 6, 7],
              [2, 3, 4, 5, 6, 7, 8]])
K = nd.array([[1, 2], [3, 4], [-1, -3]])
print(corr1d_multi_in(X, K))

batch_size = 64
d2l.download_imdb()
train_data, test_data = d2l.read_imdb('train'), d2l.read_imdb('test')
vocab = d2l.get_vocab_imdb(train_data)
train_iter = gdata.DataLoader(gdata.ArrayDataset(
    *d2l.preprocess_imdb(train_data, vocab)), batch_size, shuffle=True)
test_iter = gdata.DataLoader(gdata.ArrayDataset(
    *d2l.preprocess_imdb(test_data, vocab)), batch_size)

class TextCNN(nn.Block):
    def __init__(self, vocab, embed_size, kernel_sizes, num_channels,
                 **kwargs):
        super(TextCNN, self).__init__(**kwargs)
        self.embedding = nn.Embedding(len(vocab), embed_size)
        # 不参与训练的嵌入层
        self.constant_embedding = nn.Embedding(len(vocab), embed_size)
        self.dropout = nn.Dropout(0.5)
        self.decoder = nn.Dense(2)
        # 时序最大池化层没有权重，所以可以共用一个实例
        self.pool = nn.GlobalMaxPool1D()
        self.convs = nn.Sequential()  # 创建多个一维卷积层
        for c, k in zip(num_channels, kernel_sizes):
            self.convs.add(nn.Conv1D(c, k, activation='relu'))

    def forward(self, inputs):
        # 将两个形状是(批量大小, 词数, 词向量维度)的嵌入层的输出按词向量连结
        embeddings = nd.concat(
            self.embedding(inputs), self.constant_embedding(inputs), dim=2)
        # 根据Conv1D要求的输入格式，将词向量维，即一维卷积层的通道维，变换到前一维
        embeddings = embeddings.transpose((0, 2, 1))
        # 对于每个一维卷积层，在时序最大池化后会得到一个形状为(批量大小, 通道大小, 1)的
        # NDArray。使用flatten函数去掉最后一维，然后在通道维上连结
        encoding = nd.concat(*[nd.flatten(
            self.pool(conv(embeddings))) for conv in self.convs], dim=1)
        # 应用丢弃法后使用全连接层得到输出
        outputs = self.decoder(self.dropout(encoding))
        return outputs

embed_size, kernel_sizes, nums_channels = 100, [3, 4, 5], [100, 100, 100]
ctx = d2l.try_all_gpus()
net = TextCNN(vocab, embed_size, kernel_sizes, nums_channels)
net.initialize(init.Xavier(), ctx=ctx)

glove_embedding = text.embedding.create(
    'glove', pretrained_file_name='glove.6B.100d.txt', vocabulary=vocab)
net.embedding.weight.set_data(glove_embedding.idx_to_vec)
net.constant_embedding.weight.set_data(glove_embedding.idx_to_vec)
net.constant_embedding.collect_params().setattr('grad_req', 'null')

lr, num_epochs = 0.001, 1
trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr})
loss = gloss.SoftmaxCrossEntropyLoss()
d2l.train(train_iter, test_iter, net, loss, trainer, ctx, num_epochs)

print(d2l.predict_sentiment(net, vocab, ['this', 'movie', 'is', 'so', 'great']))
print(d2l.predict_sentiment(net, vocab, ['this', 'movie', 'is', 'so', 'bad']))