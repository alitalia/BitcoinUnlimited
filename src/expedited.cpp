// Copyright (c) 2015-2017 The Bitcoin Unlimited developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include "expedited.h"
#include "main.h"
#include "rpc/server.h"
#include "thinblock.h"
#include "tweak.h"
#include "unlimited.h"

#include <sstream>
#include <string>
#include <univalue.h>

#define NUM_XPEDITED_STORE 10

// Just save the last few expedited sent blocks so we don't resend (uint256)
static uint256 xpeditedBlkSent[NUM_XPEDITED_STORE];

// zeros on construction)
static int xpeditedBlkSendPos = 0;

bool CheckAndRequestExpeditedBlocks(CNode *pfrom)
{
    if (pfrom->nVersion >= EXPEDITED_VERSION)
    {
        BOOST_FOREACH (std::string &strAddr, mapMultiArgs["-expeditedblock"])
        {
            std::string strListeningPeerIP;
            std::string strPeerIP = pfrom->addr.ToString();
            // Add the peer's listening port if it was provided (only misbehaving clients do not provide it)
            if (pfrom->addrFromPort != 0)
            {
                // get addrFromPort
                std::ostringstream ss;
                ss << pfrom->addrFromPort;

                int pos1 = strAddr.rfind(":");
                int pos2 = strAddr.rfind("]:");
                if (pos1 <= 0 && pos2 <= 0)
                    strAddr += ':' + ss.str();

                pos1 = strPeerIP.rfind(":");
                pos2 = strPeerIP.rfind("]:");

                // Handle both ipv4 and ipv6 cases
                if (pos1 <= 0 && pos2 <= 0)
                    strListeningPeerIP = strPeerIP + ':' + ss.str();
                else if (pos1 > 0)
                    strListeningPeerIP = strPeerIP.substr(0, pos1) + ':' + ss.str();
                else
                    strListeningPeerIP = strPeerIP.substr(0, pos2) + ':' + ss.str();
            }
            else
                strListeningPeerIP = strPeerIP;

            if (strAddr == strListeningPeerIP)
            {
                if (!IsThinBlocksEnabled())
                {
                    return error("You do not have Thinblocks enabled.  You can not request expedited blocks from "
                                 "peer %s (%d)",
                        strListeningPeerIP, pfrom->id);
                }
                else if (!pfrom->ThinBlockCapable())
                {
                    return error("Thinblocks is not enabled on remote peer.  You can not request expedited blocks "
                                 "from peer %s (%d)",
                        strListeningPeerIP, pfrom->id);
                }
                else
                {
                    LogPrintf("Requesting expedited blocks from peer %s (%d).\n", strListeningPeerIP, pfrom->id);
                    pfrom->PushMessage(NetMsgType::XPEDITEDREQUEST, ((uint64_t)EXPEDITED_BLOCKS));

                    LOCK(cs_xpedited);
                    xpeditedBlkUp.push_back(pfrom);

                    return true;
                }
            }
        }
    }
    return false;
}

void HandleExpeditedRequest(CDataStream &vRecv, CNode *pfrom)
{
    uint64_t options;
    vRecv >> options;
    bool stop = ((options & EXPEDITED_STOP) != 0); // Indicates started or stopped expedited service

    if (options & EXPEDITED_BLOCKS)
    {
        LOCK(cs_xpedited);

        if (stop) // If stopping, find the array element and clear it.
        {
            LogPrint("blk", "Stopping expedited blocks to peer %s (%d).\n", pfrom->addrName.c_str(), pfrom->id);
            std::vector<CNode *>::iterator it = std::find(xpeditedBlk.begin(), xpeditedBlk.end(), pfrom);
            if (it != xpeditedBlk.end())
            {
                *it = NULL;
                pfrom->Release();
            }
        }
        else // Otherwise, add the new node to the end
        {
            std::vector<CNode *>::iterator it1 = std::find(xpeditedBlk.begin(), xpeditedBlk.end(), pfrom);
            if (it1 == xpeditedBlk.end()) // don't add it twice
            {
                unsigned int maxExpedited = GetArg("-maxexpeditedblockrecipients", 32);
                if (xpeditedBlk.size() < maxExpedited)
                {
                    LogPrint("blk", "Starting expedited blocks to peer %s (%d).\n", pfrom->addrName.c_str(), pfrom->id);

                    // find an empty array location
                    std::vector<CNode *>::iterator it =
                        std::find(xpeditedBlk.begin(), xpeditedBlk.end(), ((CNode *)NULL));
                    if (it != xpeditedBlk.end())
                        *it = pfrom;
                    else
                        xpeditedBlk.push_back(pfrom);
                    pfrom->AddRef(); // add a reference because we have added this pointer into the expedited array
                }
                else
                {
                    LogPrint("blk", "Expedited blocks requested from peer %s (%d), but I am full.\n",
                        pfrom->addrName.c_str(), pfrom->id);
                }
            }
        }
    }
    if (options & EXPEDITED_TXNS)
    {
        LOCK(cs_xpedited);

        if (stop) // If stopping, find the array element and clear it.
        {
            LogPrint("blk", "Stopping expedited transactions to peer %s (%d).\n", pfrom->addrName.c_str(), pfrom->id);
            std::vector<CNode *>::iterator it = std::find(xpeditedTxn.begin(), xpeditedTxn.end(), pfrom);
            if (it != xpeditedTxn.end())
            {
                *it = NULL;
                pfrom->Release();
            }
        }
        else // Otherwise, add the new node to the end
        {
            std::vector<CNode *>::iterator it1 = std::find(xpeditedTxn.begin(), xpeditedTxn.end(), pfrom);
            if (it1 == xpeditedTxn.end()) // don't add it twice
            {
                unsigned int maxExpedited = GetArg("-maxexpeditedtxrecipients", 32);
                if (xpeditedTxn.size() < maxExpedited)
                {
                    LogPrint("blk", "Starting expedited transactions to peer %s (%d).\n", pfrom->addrName.c_str(),
                        pfrom->id);

                    std::vector<CNode *>::iterator it =
                        std::find(xpeditedTxn.begin(), xpeditedTxn.end(), ((CNode *)NULL));
                    if (it != xpeditedTxn.end())
                        *it = pfrom;
                    else
                        xpeditedTxn.push_back(pfrom);
                    pfrom->AddRef();
                }
                else
                {
                    LogPrint("blk", "Expedited transactions requested from peer %s (%d), but I am full.\n",
                        pfrom->addrName.c_str(), pfrom->id);
                }
            }
        }
    }
}

bool IsRecentlyExpeditedAndStore(const uint256 &hash)
{
    for (int i = 0; i < NUM_XPEDITED_STORE; i++)
        if (xpeditedBlkSent[i] == hash)
            return true;

    xpeditedBlkSent[xpeditedBlkSendPos] = hash;
    xpeditedBlkSendPos++;
    if (xpeditedBlkSendPos >= NUM_XPEDITED_STORE)
        xpeditedBlkSendPos = 0;

    return false;
}

bool HandleExpeditedBlock(CDataStream &vRecv, CNode *pfrom)
{
    unsigned char hops;
    unsigned char msgType;
    vRecv >> msgType >> hops;

    if (msgType == EXPEDITED_MSG_XTHIN)
    {
        CXThinBlock thinBlock;
        vRecv >> thinBlock;
        uint256 blkHash = thinBlock.header.GetHash();
        CInv inv(MSG_BLOCK, blkHash);

        bool newBlock = false;
        unsigned int status = 0;
        {
            LOCK(cs_main);
            BlockMap::iterator mapEntry = mapBlockIndex.find(blkHash);
            CBlockIndex *blkidx = NULL;
            if (mapEntry != mapBlockIndex.end())
            {
                blkidx = mapEntry->second;
                if (blkidx)
                    status = blkidx->nStatus;
            }

            // If we do not have the block on disk or do not have the header yet then treat the block as new.
            newBlock = ((blkidx == NULL) || (!(blkidx->nStatus & BLOCK_HAVE_DATA)));
        }

        int nSizeThinBlock = ::GetSerializeSize(thinBlock, SER_NETWORK, PROTOCOL_VERSION);
        LogPrint("thin",
            "Received %s expedited thinblock %s from peer %s (%d). Hop %d. Size %d bytes. (status %d,0x%x)\n",
            newBlock ? "new" : "repeated", inv.hash.ToString(), pfrom->addrName.c_str(), pfrom->id, hops,
            nSizeThinBlock, status, status);

        // TODO: Move this section above the print once we ensure no unexpected dups.
        // Skip if we've already seen this block
        if (IsRecentlyExpeditedAndStore(blkHash))
            return true;
        if (!newBlock)
            return true;

        CValidationState state;
        if (!CheckBlockHeader(thinBlock.header, state, true))
            return false;

        // TODO: Start headers-only mining now

        SendExpeditedBlock(thinBlock, hops + 1, pfrom);

        // Process the thinblock
        thinBlock.process(pfrom, nSizeThinBlock, NetMsgType::XPEDITEDBLK);
    }
    else
    {
        return error("Received unknown (0x%x) expedited message from peer %s (%d). Hop %d.\n", msgType,
            pfrom->addrName.c_str(), pfrom->id, hops);
    }
    return true;
}

void SendExpeditedBlock(CXThinBlock &thinBlock, unsigned char hops, const CNode *skip)
{
    LOCK(cs_xpedited);
    std::vector<CNode *>::iterator end = xpeditedBlk.end();
    for (std::vector<CNode *>::iterator it = xpeditedBlk.begin(); it != end; it++)
    {
        CNode *n = *it;
        if ((n != skip) && (n != NULL)) // Don't send it back in case there is a forwarding loop
        {
            if (n->fDisconnect)
            {
                *it = NULL;
                n->Release();
            }
            else
            {
                LogPrint("thin", "Sending expedited block %s to %s.\n", thinBlock.header.GetHash().ToString(),
                    n->addrName.c_str());

                n->PushMessage(NetMsgType::XPEDITEDBLK, (unsigned char)EXPEDITED_MSG_XTHIN, hops, thinBlock);
                n->blocksSent += 1;
            }
        }
    }
}

void SendExpeditedBlock(const CBlock &block, const CNode *skip)
{
    if (!IsRecentlyExpeditedAndStore(block.GetHash()))
    {
        CXThinBlock thinBlock(block);
        SendExpeditedBlock(thinBlock, 0, skip);
    }
    // else, nothing to do
}
