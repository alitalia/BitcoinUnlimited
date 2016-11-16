#!/usr/bin/env python2
# Copyright (c) 2014-2015 The Bitcoin Core developers
# Copyright (c) 2015-2016 The Bitcoin Unlimited developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

# Exercise the getchaintips API.  We introduce a network split, work
# on chains of different lengths, and join the network together again.
# This gives us two tips, verify that it works.
import time
import random
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal
from test_framework.util import *
from test_framework.blocktools import *
import test_framework.script as script
import pdb
import sys
import logging
logging.basicConfig(format='%(asctime)s.%(levelname)s: %(message)s', level=logging.INFO)

class ExcessiveBlockTest (BitcoinTestFramework):
    def __init__(self,extended=False):
      self.extended = extended
      BitcoinTestFramework.__init__(self)

    def setup_network(self, split=False):
        self.nodes = start_nodes(4, self.options.tmpdir,timewait=60*10)
        interconnect_nodes(self.nodes)
        self.is_network_split=False
        self.sync_all()

        if 0:  # Use to create wallet with lots of addresses
          TEST_SIZE=10000
          print "Creating addresses..."
          addrs = [ self.nodes[0].getnewaddress() for _ in range(TEST_SIZE+1)]
          with open("walletAddrs.json","w") as f: 
            f.write(str(addrs))
            pdb.set_trace()

    def run_test(self):
      BitcoinTestFramework.run_test (self)

      # exact point in chain is not required
      #tips = self.nodes[0].getchaintips ()
      #assert_equal (len (tips), 1)
      #assert_equal (tips[0]['branchlen'], 0)
      #assert_equal (tips[0]['height'], 200)
      #assert_equal (tips[0]['status'], 'active')

      self.testExcessiveBlock()
      self.testExcessiveTx()

    def testExcessiveTx(self):
      TEST_SIZE=20
      logging.info("Test excessive transactions")
      if 1:
        tips = self.nodes[0].getchaintips ()
        #assert_equal (len (tips), 1)
        #assert_equal (tips[0]['branchlen'], 0)
        #assert_equal (tips[0]['height'], 200)
        #assert_equal (tips[0]['status'], 'active')

        self.nodes[0].set("net.excessiveAcceptDepth=0")
        self.nodes[1].set("net.excessiveAcceptDepth=1")
        self.nodes[2].set("net.excessiveAcceptDepth=2")
        self.nodes[3].set("net.excessiveAcceptDepth=3")

        self.nodes[0].set("net.excessiveBlock=2000000")
        self.nodes[1].set("net.excessiveBlock=2000000")
        self.nodes[2].set("net.excessiveBlock=2000000")
        self.nodes[3].set("net.excessiveBlock=2000000")

        logging.info("Cleaning up node state")
        for n in self.nodes:
          n.generate(10)
  	  self.sync_blocks()
        
        self.sync_all()
        # verify mempool is cleaned up on all nodes
	mbefore = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
	assert_equal(mbefore,[(0, 0)]*4)


        if 1:
  	  logging.info("Creating addresses...")
	  addrs = [ self.nodes[0].getnewaddress() for _ in range(TEST_SIZE+1)]
        else:
  	  logging.info("Loading addresses...")
          with open("wallet10kAddrs.json") as f: addrs = json.load(f)


        if 1:  # Test not relaying a large transaction
          wallet = self.nodes[0].listunspent()
          wallet.sort(key=lambda x: x["amount"],reverse=True)

  	  # Create a LOT of UTXOs
          logging.info("Create lots of UTXOs...")
          n=0
          group = min(100, TEST_SIZE)
          count = 0
          for w in wallet:
            count += 1
            # print count, " ",
            split_transaction(self.nodes[0], [w], addrs[n:group+n])
            n+=group
            if n >= len(addrs): n=0
	  logging.info("mine blocks")
          self.nodes[0].generate(5)  # mine all the created transactions
	  logging.info("sync all blocks and mempools")
	  self.sync_all()

          wallet = self.nodes[0].listunspent()
          wallet.sort(key=lambda x: x["amount"],reverse=True)

          logging.info("Test not relaying a large transaction")

  	  mbefore = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          assert_equal(mbefore,[(0, 0)]*4)  # we need the mempool to be empty to track that this one tx doesn't prop

  	  (tx, vin, vout, txid) = split_transaction(self.nodes[0],wallet[0:3000],[addrs[0]],txfeePer=60)
          logging.debug("Transaction Length is: ", len(binascii.unhexlify(tx)))
          assert(binascii.unhexlify(tx) > 100000) # txn has to be big for the test to work
        
  	  mbefore = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          assert_equal(mbefore[1:],[(0, 0), (0, 0), (0, 0)])  # verify that the transaction did not propagate
          assert(mbefore[0][0] > 0) # verify that the transaction is in my node

          logging.info("Test a large transaction in block < 1MB")
          largeBlock = self.nodes[0].generate(1)
          self.sync_blocks()
          counts = [ x.getblockcount() for x in self.nodes ]
          latest = counts[0]
          assert_equal(counts, [latest,latest,latest,latest]) # Verify that all nodes accepted the block, even if some of them didn't have the transaction.  They should all accept a <= 1MB block with a tx <= 1MB

  	  # mafter = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]

        if self.extended:  # this test checks the behavior of > 1MB blocks with excessive transactions.  it takes a LONG time to generate and propagate 1MB+ txs.
  	  # Create a LOT of UTXOs for the next test
          wallet = self.nodes[0].listunspent()
          wallet.sort(key=lambda x: x["amount"],reverse=True)
          logging.info("Create lots of UTXOs...")
          n=0

          for w in wallet:
            split_transaction(self.nodes[0], [w], addrs[n:100+n])
            n+=100
            if n >= len(addrs): n=0
	
          self.nodes[0].generate(1)
	  self.sync_all()

          logging.info("Building > 1MB block...")
          self.nodes[0].set("net.excessiveTxn=1000000")  # Set the excessive transaction size larger for this node so we can generate an "excessive" block for the other nodes
        
          wallet = self.nodes[0].listunspent()
          wallet.sort(key=lambda x: x["amount"],reverse=False)

          # Generate 1 MB worth of transactions        
          size = 0
          count = 0
          while size < 1000000:
            count+=1
            utxo = wallet.pop()
            outp = {}
	    outp[addrs[count%len(addrs)]] = utxo["amount"]
            txn = self.nodes[0].createrawtransaction([utxo], outp)
            signedtxn = self.nodes[0].signrawtransaction(txn)
            size += len(binascii.unhexlify(signedtxn["hex"]))
            self.nodes[0].sendrawtransaction(signedtxn["hex"])

          # Now generate a > 100kb transaction & mine it into a > 1MB block

          self.nodes[0].setminingmaxblock(2000000)
          wallet.sort(key=lambda x: x["amount"],reverse=True)
	  (tx, vin, vout, txid) = split_transaction(self.nodes[0],wallet[0:2000],[addrs[0]],txfeePer=60)
          logging.debug("Transaction Length is: ", len(binascii.unhexlify(tx)))
          # assert(binascii.unhexlify(tx) > 100000) # txn has to be big for the test to work
	  origCounts = [ x.getblockcount() for x in self.nodes ]
          mpool = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          print mpool
          largeBlock = self.nodes[0].generate(1)
          time.sleep(10) # can't sync b/c nodes won't be in sync
          mpool = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          print mpool
          counts = [ x.getblockcount() for x in self.nodes ]
          latest = counts[0]
          excess = latest-1
          #assert_equal(counts, [latest,excess,excess,excess]) 

          logging.info("Syncing node1")
          largeBlock2 = self.nodes[0].generate(1)
          while 1:
            counts = [ x.getblockcount() for x in self.nodes ]
            if counts[0] == counts[1]:  # this is a large block with lots of tx so can take a LONG time to sync on one computer
              break
            time.sleep(10) # can't sync b/c nodes won't be in sync
            print ".",
          mpool = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          print mpool
          latest = counts[0]
          assert_equal(counts, [latest,latest,excess,excess]) 
          print ""

          logging.info("Syncing node2")
          largeBlock3 = self.nodes[0].generate(1)
          while 1:
            counts = [ x.getblockcount() for x in self.nodes ]
            if counts[0] == counts[1] == counts[2]:  # this is a large block with lots of tx so can take a LONG time to sync on one computer
              break
            time.sleep(10) # can't sync b/c nodes won't be in sync
            print ".",
          mpool = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          print mpool
          counts = [ x.getblockcount() for x in self.nodes ]
          latest = counts[0]
          assert_equal(counts, [latest,latest,latest,excess]) 
          print ""

          logging.info("Syncing node3")          
          largeBlock4 = self.nodes[0].generate(1)
          while 1:
            counts = [ x.getblockcount() for x in self.nodes ]
            if counts[0] == counts[1] == counts[2]:  # this is a large block with lots of tx so can take a LONG time to sync on one computer
              break
            time.sleep(10) # can't sync b/c nodes won't be in sync
            print ".",
          mpool = [ (lambda y: (y["size"],y["bytes"]))(x.getmempoolinfo()) for x in self.nodes]
          print mpool
          counts = [ x.getblockcount() for x in self.nodes ]
          latest = counts[0]
          assert_equal(counts, [latest,latest,latest,latest]) 

    def repeatTx(self,count,node,addr,amt=1.0):
        for i in range(0,count):
          node.sendtoaddress(addr, amt)

    def testExcessiveBlock (self):

        # get spendable coins
        if 0:
          for n in self.nodes:
            n.generate(1)
            self.sync_all()
          self.nodes[0].generate(100)
	  self.sync_all()
        
 	# Set the accept depth at 1, 2, and 3 and watch each nodes resist the chain for that long
        self.nodes[1].setminingmaxblock(1000, 1)
        self.nodes[2].setminingmaxblock(1000, 2)
        self.nodes[3].setminingmaxblock(1000, 3)

        self.nodes[1].setexcessiveblock(1000, 1)
        self.nodes[2].setexcessiveblock(1000, 2)
        self.nodes[3].setexcessiveblock(1000, 3)

        logging.info("Test excessively sized block, not propagating until accept depth is exceeded")
        addr = self.nodes[3].getnewaddress()
        self.repeatTx(20,self.nodes[0],addr)
        counts = [ x.getblockcount() for x in self.nodes ]
        base = counts[0]
        logging.info("node0")
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+1,base,base,base])  

        logging.info("node1")
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        sync_blocks(self.nodes[0:2])
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+2,base+2,base,base])  

        logging.info("node2")
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        sync_blocks(self.nodes[0:3])
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+3,base+3,base+3,base])  

        logging.info("node3")
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        self.sync_all()
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+4]*4)  

        # Now generate another excessive block, but all nodes should snap right to it because they have an older excessive block
        logging.info("Test immediate propagation of additional excessively sized block, due to prior excessive")
        self.repeatTx(20,self.nodes[0],addr)
        self.nodes[0].generate(1)
        self.sync_all()
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+5]*4)  
      
        logging.info("Test daily excessive reset")
        self.nodes[0].generate(6*24)  # Now generate a day's worth of small blocks which should re-enable the node's reluctance to accept a large block
        self.nodes[0].generate(5) # plus the accept depths
        self.sync_all()
        self.repeatTx(20,self.nodes[0],addr)

        base = self.nodes[0].getblockcount()
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        counts = [ x.getblockcount() for x in self.nodes ]
        #assert_equal(counts, [base+1,349,349,349])  
        assert_equal(counts, [base+1,base,base,base])  

        self.repeatTx(20,self.nodes[0],addr)
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        sync_blocks(self.nodes[0:2])
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+2,base+2,base,base])  

        self.repeatTx(20,self.nodes[0],addr)
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        sync_blocks(self.nodes[0:3])
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+3,base+3,base+3,base])  

        self.repeatTx(20,self.nodes[0],addr)
        self.nodes[0].generate(1)
        self.sync_all()
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+4]*4)  

        self.repeatTx(20,self.nodes[0],addr)
        self.nodes[0].generate(1)
        self.sync_all()
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+5]*4)  

        logging.info("Test daily excessive reset #2")
        self.nodes[0].generate(6*24 + 10)  # Now generate a day's worth of small blocks which should re-enable the node's reluctance to accept a large block + 10 because we have to get beyond all the node's accept depths
        self.sync_all()

        # counts = [ x.getblockcount() for x in self.nodes ]
        self.nodes[1].setminingmaxblock(100000)  # not sure how big the txns will be but smaller than this 
        self.nodes[1].setexcessiveblock(100000, 1)  # not sure how big the txns will be but smaller than this 
        self.repeatTx(40,self.nodes[0],addr)
        self.sync_all()
	base = self.nodes[0].getblockcount()
        self.nodes[0].generate(1)
        time.sleep(2) #give blocks a chance to fully propagate
        sync_blocks(self.nodes[0:2])
        counts = [ x.getblockcount() for x in self.nodes ]
        assert_equal(counts, [base+1,base+1,base,base])  
      

        if self.extended: randomRange = 20
        else: randomRange = 2

        logging.info("Random test")
        random.seed(1)
        for i in range(0,randomRange):
          logging.info("round %d" % i)
          for n in self.nodes:
            size = random.randint(1,1000)*1000
            n.setminingmaxblock(size)
            n.setexcessiveblock(size, random.randint(0,10))
          addrs = [x.getnewaddress() for x in self.nodes]
          ntxs=0
          for i in range(0,random.randint(1,200)):
            try:
              self.nodes[random.randint(0,3)].sendtoaddress(addrs[random.randint(0,3)], .1)
              ntxs += 1
            except JSONRPCException: # could be spent all the txouts
              pass
          logging.debug("%d transactions" % ntxs)
          time.sleep(1)
          self.nodes[random.randint(0,3)].generate(1)
          time.sleep(1)


if __name__ == '__main__':
    
    
    if "--extended" in sys.argv:
      longTest=True
      sys.argv.remove("--extended")
      logging.info("Running extended tests")
    else:
      longTest=False

    ExcessiveBlockTest(longTest).main ()

def info(type, value, tb):
   if hasattr(sys, 'ps1') or not sys.stderr.isatty():
      # we are in interactive mode or we don't have a tty-like
      # device, so we call the default hook
      sys.__excepthook__(type, value, tb)
   else:
      import traceback, pdb
      # we are NOT in interactive mode, print the exception...
      traceback.print_exception(type, value, tb)
      print
      # ...then start the debugger in post-mortem mode.
      pdb.pm()

sys.excepthook = info

def Test():
  t = ExcessiveBlockTest()
# ,'--debug']
# "--noshutdown"
# "--tmpdir"
  bitcoinConf = {
          "debug":["net","blk","thin","lck","mempool","req","bench","evict"] }

  t.main(["--nocleanup","--noshutdown"],bitcoinConf,["wallet10k.dat",None,None,None]) # , "--tracerpc"])
