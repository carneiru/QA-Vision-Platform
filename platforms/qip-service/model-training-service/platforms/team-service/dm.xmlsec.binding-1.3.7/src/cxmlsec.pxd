cdef extern from *:
        ctypedef char const_char "const char"
        ctypedef unsigned char const_unsigned_char "const unsigned char"
        
cdef extern from 'cxmlsec.h':
        # 0 terminated utf-8 encoded
        ctypedef unsigned char xmlChar
        ctypedef xmlChar const_xmlChar "const xmlChar"

        ctypedef unsigned int xmlSecSize

        # bytes (with length specified elsewhere)
        ctypedef unsigned char xmlSecByte
        ctypedef xmlSecByte const_xmlSecByte "const xmlSecByte"

        ctypedef void * xmlDocPtr
        ctypedef void * xmlNodePtr

        int xmlSecInit() nogil
        int xmlSecCryptoAppInit(char *) nogil
        int xmlSecCryptoInit() nogil
        void xmlSecAddIDs(xmlDocPtr, xmlNodePtr, xmlChar * *) nogil
        xmlNodePtr xmlSecFindChild(xmlNodePtr, xmlChar *, xmlChar *) nogil

        cdef struct _xmlSecKeyDataKlass:
                const_xmlChar *name
                const_xmlChar *href

        ctypedef _xmlSecKeyDataKlass *xmlSecKeyDataId
        xmlSecKeyDataId xmlSecKeyDataNameId
        xmlSecKeyDataId xmlSecKeyDataValueId
        xmlSecKeyDataId xmlSecKeyDataRetrievalMethodId
        xmlSecKeyDataId xmlSecKeyDataEncryptedKeyId
        xmlSecKeyDataId xmlSecKeyDataAesId
        xmlSecKeyDataId xmlSecKeyDataDesId
        xmlSecKeyDataId xmlSecKeyDataDsaId
        xmlSecKeyDataId xmlSecKeyDataHmacId
        xmlSecKeyDataId xmlSecKeyDataRsaId
        xmlSecKeyDataId xmlSecKeyDataX509Id
        xmlSecKeyDataId xmlSecKeyDataRawX509CertId

        ctypedef void * xmlSecKeyPtr
        ctypedef enum xmlSecKeyDataFormat:
                xmlSecKeyDataFormatUnknown = 0
                xmlSecKeyDataFormatBinary = 1
                xmlSecKeyDataFormatPem = 2
                xmlSecKeyDataFormatDer = 3
                xmlSecKeyDataFormatPkcs8Pem = 4
                xmlSecKeyDataFormatPkcs8Der = 5
                xmlSecKeyDataFormatPkcs12 = 6
                xmlSecKeyDataFormatCertPem = 7
                xmlSecKeyDataFormatCertDer = 8
        ctypedef unsigned int xmlSecKeyDataType
        cdef enum:
                xmlSecKeyDataTypeUnknown = 0x0000
                xmlSecKeyDataTypeNone = 0x0000
                xmlSecKeyDataTypePublic = 0x0001
                xmlSecKeyDataTypePrivate = 0x0002
                xmlSecKeyDataTypeSymmetric = 0x0004
                xmlSecKeyDataTypeSession = 0x0008
                xmlSecKeyDataTypePermanent = 0x0010
                xmlSecKeyDataTypeTrusted = 0x0100
                xmlSecKeyDataTypeAny = 0xFFFF
                
        void xmlSecKeyDestroy(xmlSecKeyPtr) nogil
        xmlSecKeyPtr xmlSecKeyDuplicate(xmlSecKeyPtr) nogil
        xmlSecKeyPtr xmlSecCryptoAppKeyLoad(const_char *, xmlSecKeyDataFormat, const_char *, void *, void *) nogil
        int xmlSecCryptoAppKeyCertLoad(xmlSecKeyPtr, const_char *, xmlSecKeyDataFormat) nogil
        xmlSecKeyPtr xmlSecCryptoAppKeyLoadMemory(const_unsigned_char *, int, xmlSecKeyDataFormat, const_char *, void *, void *) nogil
        xmlSecKeyPtr xmlSecKeyReadBinaryFile(xmlSecKeyDataId, const_char *) nogil
        xmlSecKeyPtr xmlSecKeyReadMemory(xmlSecKeyDataId, const_unsigned_char *, size_t) nogil
        xmlSecKeyPtr xmlSecKeyGenerate(xmlSecKeyDataId, size_t, xmlSecKeyDataType) nogil
        int xmlSecKeySetName(xmlSecKeyPtr, const_xmlChar *) nogil
        const_xmlChar * xmlSecKeyGetName(xmlSecKeyPtr) nogil

        cdef struct _xmlSecBuffer:
                unsigned char * data
                size_t size
##              size_t maxSize
##              xmlSecAllocMode allocMode
        
        ctypedef _xmlSecBuffer *xmlSecBufferPtr

        ctypedef unsigned int xmlSecTransformUsage
        cdef enum:
                xmlSecTransformUsageUnknown=0x0000
                xmlSecTransformUsageDSigTransform=0x0001
                xmlSecTransformUsageC14NMethod=0x0002
                xmlSecTransformUsageDigestMethod=0x0004
                xmlSecTransformUsageSignatureMethod=0x0008
                xmlSecTransformUsageEncryptionMethod=0x0010
                xmlSecTransformUsageAny=0xFFFF

        cdef struct _xmlSecTransformKlass:
                const_xmlChar * name
                const_xmlChar * href
                xmlSecTransformUsage usage
                
        ctypedef _xmlSecTransformKlass *xmlSecTransformId
        xmlSecTransformId xmlSecTransformInclC14NId
        xmlSecTransformId xmlSecTransformInclC14NWithCommentsId
        xmlSecTransformId xmlSecTransformInclC14N11Id
        xmlSecTransformId xmlSecTransformInclC14N11WithCommentsId
        xmlSecTransformId xmlSecTransformExclC14NId
        xmlSecTransformId xmlSecTransformExclC14NWithCommentsId
        xmlSecTransformId xmlSecTransformEnvelopedId
        xmlSecTransformId xmlSecTransformXPathId
        xmlSecTransformId xmlSecTransformXPath2Id
        xmlSecTransformId xmlSecTransformXPointerId
        xmlSecTransformId xmlSecTransformXsltId
        xmlSecTransformId xmlSecTransformRemoveXmlTagsC14NId
        xmlSecTransformId xmlSecTransformVisa3DHackId
        xmlSecTransformId xmlSecTransformAes128CbcId
        xmlSecTransformId xmlSecTransformAes192CbcId
        xmlSecTransformId xmlSecTransformAes256CbcId
        xmlSecTransformId xmlSecTransformKWAes128Id
        xmlSecTransformId xmlSecTransformKWAes192Id
        xmlSecTransformId xmlSecTransformKWAes256Id
        xmlSecTransformId xmlSecTransformDes3CbcId
        xmlSecTransformId xmlSecTransformKWDes3Id
        xmlSecTransformId xmlSecTransformDsaSha1Id
        xmlSecTransformId xmlSecTransformHmacMd5Id
        xmlSecTransformId xmlSecTransformHmacRipemd160Id
        xmlSecTransformId xmlSecTransformHmacSha1Id
        xmlSecTransformId xmlSecTransformHmacSha224Id
        xmlSecTransformId xmlSecTransformHmacSha256Id
        xmlSecTransformId xmlSecTransformHmacSha384Id
        xmlSecTransformId xmlSecTransformHmacSha512Id
        xmlSecTransformId xmlSecTransformMd5Id
        xmlSecTransformId xmlSecTransformRipemd160Id
        xmlSecTransformId xmlSecTransformRsaMd5Id
        xmlSecTransformId xmlSecTransformRsaRipemd160Id
        xmlSecTransformId xmlSecTransformRsaSha1Id
        xmlSecTransformId xmlSecTransformRsaSha224Id
        xmlSecTransformId xmlSecTransformRsaSha256Id
        xmlSecTransformId xmlSecTransformRsaSha384Id
        xmlSecTransformId xmlSecTransformRsaSha512Id
        xmlSecTransformId xmlSecTransformRsaPkcs1Id
        xmlSecTransformId xmlSecTransformRsaOaepId
        xmlSecTransformId xmlSecTransformSha1Id
        xmlSecTransformId xmlSecTransformSha224Id
        xmlSecTransformId xmlSecTransformSha256Id
        xmlSecTransformId xmlSecTransformSha384Id
        xmlSecTransformId xmlSecTransformSha512Id

#       transforms and transform contexts (partial)
        ctypedef enum xmlSecTransformStatus:
               xmlSecTransformStatusNone = 0 
               xmlSecTransformStatusWorking
               xmlSecTransformStatusFinished
               xmlSecTransformStatusOk
               xmlSecTransformStatusFail 

        ctypedef enum xmlSecTransformOperation:
                xmlSecTransformOperationNone = 0
                xmlSecTransformOperationEncode
                xmlSecTransformOperationDecode
                xmlSecTransformOperationSign
                xmlSecTransformOperationVerify
                xmlSecTransformOperationEncrypt
                xmlSecTransformOperationDecrypt

        cdef struct _xmlSecTransformCtx:
                xmlSecBufferPtr result
                xmlSecTransformStatus status

        ctypedef _xmlSecTransformCtx xmlSecTransformCtx
        ctypedef _xmlSecTransformCtx *xmlSecTransformCtxPtr
 
        cdef struct _xmlSecKeyReq:
                pass

        ctypedef _xmlSecKeyReq xmlSecKeyReq
        ctypedef xmlSecKeyReq *xmlSecKeyReqPtr

        cdef struct _xmlSecTransform:
                xmlSecTransformOperation operation
                xmlSecTransformStatus status

        ctypedef _xmlSecTransform *xmlSecTransformPtr

        xmlSecTransformPtr xmlSecTransformCtxCreateAndAppend(
                 xmlSecTransformCtxPtr, xmlSecTransformId
                 ) nogil
        int xmlSecTransformSetKey(xmlSecTransformPtr, xmlSecKeyPtr) nogil
        int xmlSecTransformSetKeyReq(xmlSecTransformPtr, xmlSecKeyReqPtr) nogil
        int xmlSecTransformVerify(xmlSecTransformPtr, const_xmlSecByte*, xmlSecSize, xmlSecTransformCtxPtr) nogil
        int xmlSecTransformCtxBinaryExecute(
                 xmlSecTransformCtxPtr, const_xmlSecByte*, xmlSecSize
                 ) nogil

        ctypedef void *xmlSecKeysMngrPtr
        xmlSecKeysMngrPtr xmlSecKeysMngrCreate() nogil
        void xmlSecKeysMngrDestroy(xmlSecKeysMngrPtr) nogil
        int xmlSecCryptoAppDefaultKeysMngrInit(xmlSecKeysMngrPtr) nogil
        int xmlSecCryptoAppDefaultKeysMngrAdoptKey(xmlSecKeysMngrPtr, xmlSecKeyPtr) nogil
        int xmlSecCryptoAppKeysMngrCertLoad(xmlSecKeysMngrPtr, char * filename, xmlSecKeyDataFormat, xmlSecKeyDataType) nogil
        int xmlSecCryptoAppKeysMngrCertLoadMemory(xmlSecKeysMngrPtr, const_unsigned_char *, size_t, xmlSecKeyDataFormat, xmlSecKeyDataType) nogil

        ctypedef void * xmlSecPtrList
        ctypedef xmlSecPtrList * xmlSecPtrListPtr
        ctypedef void * xmlSecPtr

        int xmlSecPtrListAdd(xmlSecPtrListPtr, xmlSecPtr) nogil
        int xmlSecPtrListEmpty(xmlSecPtrListPtr) nogil

        cdef struct xmlSecKeyInfoCtx:
                xmlSecPtrList enabledKeyData
                xmlSecKeyReq keyReq

                
        ctypedef enum xmlSecDSigStatus:
                xmlSecDSigStatusUnknown = 0
                xmlSecDSigStatusSucceeded = 1
                xmlSecDSigStatusInvalid = 2

        struct _xmlSecDSigCtx:
##                void * userData
##                unsigned int flags
##                unsigned int flags2
                xmlSecKeyInfoCtx keyInfoReadCtx
##                xmlSecKeyInfoCtx keyInfoWriteCtx
                xmlSecTransformCtx transformCtx
##                xmlSecTransformUriType enabledReferenceUris
##                xmlSecPtrListPtr enabledReferenceTransforms
##                xmlSecTransformCtxPreExecuteCallback referencePreExecuteCallback
##                xmlSecTransformId defSignMethodId
##                xmlSecTransformId defC14NMethodId
##                xmlSecTransformId defDigestMethodId
                xmlSecKeyPtr signKey
                xmlSecTransformOperation operation
##                xmlSecBufferPtr result
                xmlSecDSigStatus status
                xmlSecTransformPtr signMethod
##                xmlSecTransformPtr c14nMethod
##                xmlSecTransformPtr preSignMemBufMethod
##                xmlNodePtr signValueNode
##                xmlChar * id
##                xmlSecPtrList signedInfoReferences
##                xmlSecPtrList manifestReferences
##                void * reserved0
##                void * reserved1
        ctypedef _xmlSecDSigCtx * xmlSecDSigCtxPtr
        xmlSecDSigCtxPtr xmlSecDSigCtxCreate(xmlSecKeysMngrPtr) nogil
        int xmlSecDSigCtxSign(xmlSecDSigCtxPtr, xmlNodePtr) nogil
        int xmlSecDSigCtxVerify(xmlSecDSigCtxPtr, xmlNodePtr) nogil
        int xmlSecDSigCtxEnableReferenceTransform(xmlSecDSigCtxPtr, xmlSecTransformId) nogil
        int xmlSecDSigCtxEnableSignatureTransform(xmlSecDSigCtxPtr, xmlSecTransformId) nogil
        void xmlSecDSigCtxDestroy(xmlSecDSigCtxPtr) nogil

        unsigned int XMLSEC_ENC_RETURN_REPLACED_NODE

        cdef struct _xmlSecEncCtx:
##              void * userData
              unsigned int flags
##              unsigned int flags2
##              xmlEncCtxMode mode
##              xmlSecKeyInfoCtx keyInfoReadCtx
##              xmlSecKeyInfoCtx keyInfoWriteCtx
##              xmlSecTransformCtx transformCtx
##              xmlSecTransformId defEncMethodId
              xmlSecKeyPtr encKey
##              xmlSecTransformOperation operation
              xmlSecBufferPtr result
##              int resultBase64Encoded
              bint resultReplaced
##              xmlSecTransformPtr encMethod
##              xmlChar * id
##              xmlChar * type
##              xmlChar * mimeType
##              xmlChar * encoding
##              xmlChar * recipient
##              xmlChar * carriedKeyName
##              xmlNodePtr encDataNode
##              xmlNodePtr encMethodNode
##              xmlNodePtr keyInfoNode
##              xmlNodePtr cipherValueNode
              xmlNodePtr replacedNodeList
##              void * reserved1
        ctypedef _xmlSecEncCtx * xmlSecEncCtxPtr
        xmlSecEncCtxPtr xmlSecEncCtxCreate(xmlSecKeysMngrPtr) nogil
        void xmlSecEncCtxDestroy(xmlSecEncCtxPtr) nogil
        int xmlSecEncCtxBinaryEncrypt(xmlSecEncCtxPtr, xmlNodePtr, const_unsigned_char *, size_t) nogil
        int xmlSecEncCtxXmlEncrypt(xmlSecEncCtxPtr, xmlNodePtr, xmlNodePtr) nogil
        int xmlSecEncCtxUriEncrypt(xmlSecEncCtxPtr, xmlNodePtr, xmlChar *) nogil
        int xmlSecEncCtxDecrypt(xmlSecEncCtxPtr, xmlNodePtr) nogil

        void xmlSecErrorsSetCallback(void *callback) nogil

        int xmlSecKeyMatch(xmlSecKeyPtr, const_xmlChar *, xmlSecKeyReqPtr)
