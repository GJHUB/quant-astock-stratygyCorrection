from stock_pool import get_training_stock_pool, build_stock_pool
train=get_training_stock_pool()
test=build_stock_pool()
print('TRAIN_COUNT',len(train))
print('TEST_COUNT',len(test))
print('TRAIN_TOP10',train[:10])
print('TEST_TOP10',test[:10])
