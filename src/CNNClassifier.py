import os, time
import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data


class MNISTLoader:
    def __init__(self):
        self.data = input_data.read_data_sets('MNIST_data')
        self.num_classes = 10
        self.image_size = 28
        self.image_pixels = self.image_size ** 2


class CNNClassifier:
    sess = None

    def __init__(self, learning_rate=0.01, max_steps=200, batch_size=100, log_dir='log', dropout_prob=0.5,
                 restore_model_path=r'\tmp\model.ckpt', dataset=MNISTLoader()):
        """"
        Args: 
            learning_rate: Initial learning rate.
            max_steps: Number of steps to run trainer.
            batch_size: Batch size.  Must divide evenly into the dataset sizes.
            log_dir: Directory to put the log data.
            dropout_prob: Dropout probability.
            restore_model_path: Restore model path. 
            dataset: Data provider.
        """

        self.learning_rate = learning_rate
        self.max_steps = max_steps
        self.batch_size = batch_size
        self.log_dir = log_dir
        self.dropout_prob = dropout_prob
        self.restore_model_path = os.getcwd() + restore_model_path

        self.dataset = dataset

    def restore_model(self):
        with tf.Graph().as_default():
            if os.path.exists(os.path.exists(self.restore_model_path + '.meta')):
                saver = tf.train.Saver()
                tf.reset_default_graph()
                self.sess = tf.Session()
                saver.restore(self.sess, self.restore_model_path)
            else:
                self.run_training()

    def run_training(self):
        images_placeholder, labels_placeholder = self.placeholder_inputs()
        logits, keep_prob = self.inference(images_placeholder)
        loss = self.loss(logits, labels_placeholder)
        train_op = self.training(loss, self.learning_rate)
        eval_correct = self.evaluation(logits, labels_placeholder)

        summary = tf.summary.merge_all()
        self.sess = tf.Session()
        summary_writer = tf.summary.FileWriter(self.log_dir, self.sess.graph)

        init_op = tf.global_variables_initializer()
        saver = tf.train.Saver()
        self.sess.run(init_op)

        for step in range(self.max_steps):
            start_time = time.time()

            feed_dict = self.fill_feed_dict(self.dataset.data.train, images_placeholder, labels_placeholder, keep_prob,
                                            self.dropout_prob)
            activations, loss_value = self.sess.run([train_op, loss], feed_dict=feed_dict)

            duration = time.time() - start_time

            if step % 100 == 0:  # log
                print('Step %d: loss = %.2f (%.3f sec)' % (step, loss_value, duration))
                # Update the events file.
                summary_str = self.sess.run(summary, feed_dict=feed_dict)
                summary_writer.add_summary(summary_str, step)
                summary_writer.flush()

            if (step + 1) % 1000 == 0 or (step + 1) == self.max_steps:  # save a checkpoint
                print('Training Data Eval:')
                self.do_eval(eval_correct, images_placeholder, labels_placeholder, self.dataset.data.train, keep_prob,
                             self.dropout_prob)
                print('Validation Data Eval:')
                self.do_eval(eval_correct, images_placeholder, labels_placeholder, self.dataset.data.validation,
                             keep_prob, 1.0)
                print('Test Data Eval:')
                self.do_eval(eval_correct, images_placeholder, labels_placeholder, self.dataset.data.test, keep_prob,
                             1.0)

        save_path = saver.save(self.sess, self.restore_model_path)
        print('Model saved in file: %s' % save_path)

    def placeholder_inputs(self):
        images_placeholder = tf.placeholder(tf.float32, shape=(self.batch_size, self.dataset.image_pixels))
        labels_placeholder = tf.placeholder(tf.int32, shape=self.batch_size)

        return images_placeholder, labels_placeholder

    def fill_feed_dict(self, data, images_pl, labels_pl, keep_prob, dropout_prob):
        batch = data.next_batch(self.batch_size)

        return {
            images_pl: batch[0],
            labels_pl: batch[1],
            keep_prob: dropout_prob
        }

    def do_eval(self, eval_correct, images_placeholder, labels_placeholder, data_set, keep_prob, dropout_prob):
        true_count = 0
        steps_per_epoch = data_set.num_examples // self.batch_size
        num_examples = steps_per_epoch * self.batch_size

        for step in range(steps_per_epoch):
            feed_dict = self.fill_feed_dict(data_set, images_placeholder, labels_placeholder, keep_prob, dropout_prob)
            true_count += self.sess.run(eval_correct, feed_dict=feed_dict)
        precision = float(true_count) / num_examples
        print('Num examples: %d  Num correct: %d  Precision @ 1: %0.04f' % (num_examples, true_count, precision))

    def inference(self, images):
        with tf.name_scope('reshape'):
            x_image = tf.reshape(images, shape=[-1, self.dataset.image_size, self.dataset.image_size, 1])

        with tf.name_scope('conv1'):
            W_conv1 = self.weight_variables([5, 5, 1, 32])
            b_conv1 = self.bias_variable([32])
            h_conv1 = tf.nn.relu(self.conv2d(x_image, W_conv1) + b_conv1)

        with tf.name_scope('pool1'):
            h_pool1 = self.max_pool_2x2(h_conv1)

        with tf.name_scope('conv2'):
            W_conv2 = self.weight_variables([5, 5, 32, 64])
            b_conv2 = self.bias_variable([64])
            h_conv2 = tf.nn.relu(self.conv2d(h_pool1, W_conv2) + b_conv2)

        with tf.name_scope('pool2'):
            h_pool2 = self.max_pool_2x2(h_conv2)

        with tf.name_scope('fc1'):
            W_fc1 = self.weight_variables([7 * 7 * 64, 1024])
            b_fc1 = self.bias_variable([1024])
            h_fc1 = tf.nn.relu(tf.matmul(tf.reshape(h_pool2, [-1, 7 * 7 * 64]), W_fc1) + b_fc1)

        with tf.name_scope('dropout'):
            keep_prob = tf.placeholder(tf.float32)
            h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)

        with tf.name_scope('fc2'):
            W_fc2 = self.weight_variables([1024, self.dataset.num_classes])
            b_fc2 = self.bias_variable([self.dataset.num_classes])

            y_conv = tf.matmul(h_fc1_drop, W_fc2) + b_fc2
            # y_conv = tf.matmul(h_fc1, W_fc2) + b_fc2

        return y_conv, keep_prob

    @staticmethod
    def loss(logits, labels):
        labels = tf.to_int64(labels)
        cross_entropy = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=labels, logits=logits, name='xentropy')

        return tf.reduce_mean(cross_entropy, name='xentropy_mean')

    @staticmethod
    def training(loss, learning_rate):
        tf.summary.scalar(name='loss', tensor=loss)
        optimizer = tf.train.AdamOptimizer(1e-4)
        global_step = tf.Variable(0, name='global_step')
        train_op = optimizer.minimize(loss, global_step=global_step)

        return train_op

    @staticmethod
    def evaluation(logits, labels):
        correct = tf.nn.in_top_k(logits, labels, 1)

        return tf.reduce_sum(tf.cast(correct, tf.int32))

    @staticmethod
    def conv2d(x, W):
        return tf.nn.conv2d(input=x, filter=W, strides=[1, 1, 1, 1], padding='SAME')

    @staticmethod
    def max_pool_2x2(x):
        return tf.nn.max_pool(value=x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME')

    @staticmethod
    def weight_variables(shape):
        return tf.Variable(initial_value=tf.truncated_normal(shape, stddev=.1))

    @staticmethod
    def bias_variable(shape):
        return tf.Variable(tf.constant(value=.1, dtype=tf.float32, shape=shape))