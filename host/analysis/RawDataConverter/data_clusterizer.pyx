# distutils: language = c++
# distutils: sources = Basis.cpp Clusterizer.cpp

import numpy as np
cimport numpy as np
from libcpp cimport bool    #to be able to use bool variables

np.import_array()   #if array is used it has to be imported, otherwise possible runtime error
  
cdef extern from "Basis.h":
    cdef cppclass Basis:
        Basis()
    
cdef packed struct numpy_hit_info:
    np.uint32_t eventNumber  #event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
    np.uint32_t triggerNumber #external trigger number for read out system
    np.uint8_t relativeBCID #relative BCID value (unsigned char: 0 to 255)
    np.uint16_t LVLID   #LVL1ID (unsigned short int: 0 to 65.535)
    np.uint8_t column       #column value (unsigned char: 0 to 255)
    np.uint16_t row     #row value (unsigned short int: 0 to 65.535)
    np.uint8_t tot          #tot value (unsigned char: 0 to 255)
    np.uint16_t BCID    #absolute BCID value (unsigned short int: 0 to 65.535)
    np.uint8_t triggerStatus#event trigger status
    np.uint32_t serviceRecord #event service records
    np.uint8_t eventStatus #event status value (unsigned char: 0 to 255)
     
cdef packed struct numpy_cluster_hit_info:
    np.uint32_t eventNumber  #event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
    np.uint32_t triggerNumber #external trigger number for read out system
    np.uint8_t relativeBCID #relative BCID value (unsigned char: 0 to 255)
    np.uint16_t LVLID   #LVL1ID (unsigned short int: 0 to 65.535)
    np.uint8_t column       #column value (unsigned char: 0 to 255)
    np.uint16_t row     #row value (unsigned short int: 0 to 65.535)
    np.uint8_t tot          #tot value (unsigned char: 0 to 255)
    np.uint16_t BCID    #absolute BCID value (unsigned short int: 0 to 65.535)
    np.uint8_t triggerStatus#event trigger status
    np.uint32_t serviceRecord #event service records
    np.uint8_t eventStatus #event status value (unsigned char: 0 to 255)
    np.uint16_t clusterID # the cluster id of the hit
    np.uint8_t isSeed # flag to mark seed pixel
     
cdef packed struct numpy_cluster_info:
    np.uint32_t eventNumber # event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
    np.uint16_t ID # the cluster id of the cluster
    np.uint16_t size # sum tot of all cluster hits
    np.uint16_t Tot # sum tot of all cluster hits
    np.float32_t charge # sum charge of all cluster hits
    np.uint8_t seed_column # column value (unsigned char: 0 to 255)
    np.uint16_t seed_row # row value (unsigned short int: 0 to 65.535)
    np.uint8_t eventStatus # event status value (unsigned char: 0 to 255)
          
cdef extern from "Clusterizer.h":
    cdef cppclass HitInfo:
        HitInfo()
    cdef cppclass ClusterHitInfo:
        ClusterHitInfo()
    cdef cppclass ClusterInfo:
        ClusterInfo()
    cdef cppclass Clusterizer(Basis):
        Clusterizer() except +
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)
         
        void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits)
         
        void setClusterHitInfoArray(ClusterHitInfo*& rClusterHitInfo, const unsigned int& rSize)
        void setClusterInfoArray(ClusterInfo*& rClusterHitInfo, const unsigned int& rSize)
        void setXclusterDistance(const unsigned int& pDx)
        void setYclusterDistance(const unsigned int&  pDy)
        void setBCIDclusterDistance(const unsigned int&  pDbCID)
        void setMinClusterHits(const unsigned int&  pMinNclusterHits)
        void setMaxClusterHits(const unsigned int&  pMaxNclusterHits)
        void setMaxClusterHitTot(const unsigned int&  pMaxClusterHitTot)  
#         
        #void clusterize()
#         
        unsigned int getNclusters()
        void test()

cdef class PyDataClusterizer:
    cdef Clusterizer* thisptr      # hold a C++ instance which we're wrapping
    def __cinit__(self):
        self.thisptr = new Clusterizer()
    def __dealloc__(self):
        del self.thisptr
        
    def set_debug_output(self,toggle):
        self.thisptr.setDebugOutput(<bool> toggle)
    def set_info_output(self,toggle):
        self.thisptr.setInfoOutput(<bool> toggle)
    def set_warning_output(self,toggle):
        self.thisptr.setWarningOutput(<bool> toggle)
    def set_error_output(self,toggle):
        self.thisptr.setErrorOutput(<bool> toggle)
        
    def add_hits(self, np.ndarray[numpy_hit_info, ndim=1] hit_info):
        self.thisptr.addHits(<HitInfo*&> hit_info.data, <unsigned int> hit_info.shape[0])
        
    def set_cluster_hit_info_array(self, np.ndarray[numpy_cluster_hit_info, ndim=1] cluster_hit_info):
        self.thisptr.setClusterHitInfoArray(<ClusterHitInfo*&> cluster_hit_info.data, <const unsigned int&> cluster_hit_info.shape[0])     
    def set_cluster_info_array(self, np.ndarray[numpy_cluster_info, ndim=1] cluster_info):
        self.thisptr.setClusterInfoArray(<ClusterInfo*&> cluster_info.data, <const unsigned int&> cluster_info.shape[0])
    def set_x_cluster_distance(self,value):
        self.thisptr.setXclusterDistance(<const unsigned int&> value)
    def set_y_cluster_distance(self,value):
        self.thisptr.setYclusterDistance(<const unsigned int&> value)
    def set_bcid_cluster_distance(self,value):
        self.thisptr.setBCIDclusterDistance(<const unsigned int&> value)
    def set_min_cluster_hits(self,value):
        self.thisptr.setMinClusterHits(<const unsigned int&> value)
    def set_max_cluster_hits(self,value):
        self.thisptr.setMaxClusterHits(<const unsigned int&> value)
    def set_max_cluster_hit_tot(self,value):
        self.thisptr.setMaxClusterHitTot(<const unsigned int&>  value)
         
    def get_n_clusters(self):
        return <unsigned int> self.thisptr.getNclusters()
    def test(self):
        self.thisptr.test()