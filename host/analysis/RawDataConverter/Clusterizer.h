/*
 * 4 July 2012, Bonn, pohl@physik.uni-bonn.de
 * 17.10.2013 changes done to use the clusterizer into phython usable c++ code via cython
 *
 * This is a simple and fast clusterizer. With a run time that is linearily dependend from:
 * _dx*_dy*_DbCID*number of hits
 *   _dx,_dy are the x,y-step sizes in pixel to search around a hit for additional hits
 *   _DbCID is the BCID window hits are clustered together
 *   number of hits per trigger/event is usually <10
 *
 * The basic idea is:
 * - use an array that is looped over only if hits are inside. Per trigger you have usually < 10 hits.
 *   Methods: Clusterize() for looping over the array
 * - start at one hit position and search around it with a distance of _dx,_dy (8 directions: up, up right, right ...) and _DbCID
 * 	Methods: Clusterize() for looping over the hit array and calling SearchNextHits() for finding next hits belonging to the clusters
 * - only increase the search distance in a certain direction (until _dx, _dy, _DbCID) if no hit was found in this direction already
 *   Method: SearchNextHits() does this
 * - do this iteratively and delete hits from the map if they are added to a cluster
 *   Method: SearchNextHits() deletes hits from the hit map if they are assigned to a cluster
 * - if the hit map is empty all hits are assigned to cluster, abort then
 * 	Method: Clusterize() does this
 *
 * 	The clusterizer can either be filled externally with hits (addHit method) or it can extract the hits from the
 * 	SRAM data including persistance check (clusterRawData method)
 */

#pragma once

//#include <set>

#include "Basis.h"
#include "defines.h"

class Clusterizer: public Basis
{
public:
	Clusterizer(void);
	~Clusterizer(void);

	void setClusterHitInfoArray(ClusterHitInfo*& rClusterHitInfo, const unsigned int& rSize);	//set pointer to the cluster hit array to be filled
	void setClusterInfoArray(ClusterInfo*& rClusterHitInfo, const unsigned int& rSize);	//set pointer to the cluster array to be filled

	void setXclusterDistance(const unsigned int& pDx);							//sets the x distance between two hits that they belong to one cluster
	void setYclusterDistance(const unsigned int&  pDy);							//sets the x distance between two hits that they belong to one cluster
	void setBCIDclusterDistance(const unsigned int&  pDbCID);					//sets the BCID depth between two hits that they belong to one cluster
	void setMinClusterHits(const unsigned int&  pMinNclusterHits);				//minimum hits per cluster allowed, otherwise cluster omitted
	void setMaxClusterHits(const unsigned int&  pMaxNclusterHits);				//maximal hits per cluster allowed, otherwise cluster omitted
	void setMaxClusterHitTot(const unsigned int&  pMaxClusterHitTot);			//maximal tot for a cluster hit, otherwise cluster omitted
	void setLateHitTot(const unsigned int&  pLateHitTot);						//minimum tot a hit is considered to be late/small

	void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits);		//add hits to cluster, starts clustering, warning hits have to be aligned at events

	unsigned int getNclusters();										//returns the number of clusters//main function to start the clustering of the hit array

	void test();

private:
	void addHit(const unsigned int& pHitIndex);	//add hit with index pHitIndex of the input hit array
	inline void searchNextHits(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);			//search for a hit next to the actual one in time (BCIDs) and space (col, row)
	inline bool deleteHit(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);				//delete hit at position pCol,pRow from hit map, returns true if hit array is empty
	inline bool hitExists(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);				//check if the hit exists
	void initChargeCalibMap();											//sets the calibration map to all entries = 0
	void addClusterToResults();											//adds the actual cluster data to the result arrays
	bool clusterize();

	void clearClusterMaps();											//reset the cluster maps
	void clearActualClusterData();
	void clearActualEventVariables();
	void showHits();													//shows the hit in the hit map for debugging

	void allocateHitMap();
	void initHitMap();													//sets the hit map to no hit = all entries = -1
	void clearHitMap();
	void deleteHitMap();

	void allocateHitIndexMap();
	void deleteHitIndexMap();

	void allocateChargeMap();
	void deleteChargeMap();

	void addCluster();													//adds the actual cluster to the _clusterInfo array

	//input data structure
	HitInfo* _hitInfo;

	//output data structures, have to be allocated externally
	ClusterHitInfo* _clusterHitInfo;
	unsigned int _clusterHitInfoSize;
	unsigned int _NclustersHits;
	ClusterInfo* _clusterInfo;
	unsigned int _clusterInfoSize;
	unsigned int _Nclusters;

	//cluster results
//	unsigned int _clusterTots[__MAXTOTBINS][__MAXCLUSTERHITSBINS];		//array containing the cluster tots/cluster size for histogramming
//	unsigned int _clusterCharges[__MAXCHARGEBINS][__MAXCLUSTERHITSBINS];//array containing the cluster tots/cluster size for histogramming
//	unsigned int _clusterHits[__MAXCLUSTERHITSBINS];					//array containing the cluster number of hits for histogramming
//	unsigned int _clusterPosition[__MAXPOSXBINS][__MAXPOSYBINS];		//array containing the cluster x positions for histogramming

	//data arrays for one event
	short int* _hitMap;       											//2d hit histogram for each relative BCID (in total 3d, linearly sorted via col, row, rel. BCID)
//	short int _hitMap[RAW_DATA_MAX_COLUMN][RAW_DATA_MAX_ROW][__MAXBCID];//array containing the hits TOT value for max 16 BCIDs
//	unsigned int _hitIndexMap[RAW_DATA_MAX_COLUMN][RAW_DATA_MAX_ROW][__MAXBCID];//array containing the hit indices from the input hit array
	unsigned int* _hitIndexMap;
	float* _chargeMap;													//array containing the lookup charge values for each pixel and TOT
//	float _chargeMap[RAW_DATA_MAX_COLUMN][RAW_DATA_MAX_ROW][14];		//array containing the lookup charge values for each pixel and TOT

	//cluster settings
	unsigned short _dx;													//max distance in x between two hits that they belong to a cluster
	unsigned short _dy;													//max distance in y between two hits that they belong to a cluster
	unsigned short _DbCID; 												//time window in BCIDs the clustering is done
	unsigned short _maxClusterHitTot; 									//the maximum number of cluster hit tot allowed, if exeeded cluster is omitted
	unsigned short _minClusterHits; 									//the minimum number of cluster hits allowed, if exeeded clustering aborted
	unsigned short _maxClusterHits; 									//the maximum number of cluster hits allowed, if exeeded clustering aborted
	unsigned int _runTime; 												//artificial value to represent the run time needed for clustering
	unsigned int _lateHitTot;											//the tot value a hit is considered to be small (usually 14)

	//actual clustering variables
	unsigned int _nHits;												//number of hits for the actual event data to cluster
	unsigned short _minColHitPos;										//minimum column with a hit for the actual event data
	unsigned short _maxColHitPos;										//maximum column with a hit for the actual event data
	unsigned short _minRowHitPos;										//minimum row with a hit for the actual event data
	unsigned short _maxRowHitPos;										//maximum row with a hit for the actual event data
	short _bCIDfirstHit;										        //relative start BCID value of the first hit [0:15]
	short _bCIDlastHit;										            //relative stop BCID value of the last hit [0:15]
	unsigned int _actualClusterTot;										//temporary value holding the total tot value of the actual cluster
	unsigned int _actualClusterMaxTot;									//temporary value holding the maximum tot value of the actual cluster
	unsigned int _actualRelativeClusterBCID; 							//temporary value holding the relative BCID start value of the actual cluster [0:15]
	unsigned short _actualClusterID;
	unsigned short _actualClusterSize;									//temporary value holding the total hit number of the actual cluster
	unsigned short _actualClusterSeed_column;
	unsigned short _actualClusterSeed_row;
	unsigned short _actualClusterSeed_relbcid;
	float _actualClusterX;												//temporary value holding the x position of the actual cluster
	float _actualClusterY;												//temporary value holding the y position of the actual cluster
	float _actualClusterCharge;											//temporary value holding the total charge value of the actual cluster

	//actual event variables
	unsigned int _actualEventNumber;  //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
	unsigned char _actualEventStatus;

	bool _abortCluster;													//set to true if one cluster TOT hit exeeds _maxClusterHitTot, cluster is not added to the result array
};
