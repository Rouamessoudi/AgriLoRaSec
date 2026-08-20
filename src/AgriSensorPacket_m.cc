//
// Generated file, do not edit! Created by opp_msgtool 6.3 from AgriSensorPacket.msg.
//

// Disable warnings about unused variables, empty switch stmts, etc:
#ifdef _MSC_VER
#  pragma warning(disable:4101)
#  pragma warning(disable:4065)
#endif

#if defined(__clang__)
#  pragma clang diagnostic ignored "-Wshadow"
#  pragma clang diagnostic ignored "-Wconversion"
#  pragma clang diagnostic ignored "-Wunused-parameter"
#  pragma clang diagnostic ignored "-Wc++98-compat"
#  pragma clang diagnostic ignored "-Wunreachable-code-break"
#  pragma clang diagnostic ignored "-Wold-style-cast"
#elif defined(__GNUC__)
#  pragma GCC diagnostic ignored "-Wshadow"
#  pragma GCC diagnostic ignored "-Wconversion"
#  pragma GCC diagnostic ignored "-Wunused-parameter"
#  pragma GCC diagnostic ignored "-Wold-style-cast"
#  pragma GCC diagnostic ignored "-Wsuggest-attribute=noreturn"
#  pragma GCC diagnostic ignored "-Wfloat-conversion"
#endif

#include <iostream>
#include <sstream>
#include <memory>
#include <type_traits>
#include "AgriSensorPacket_m.h"

namespace omnetpp {

// Template pack/unpack rules. They are declared *after* a1l type-specific pack functions for multiple reasons.
// They are in the omnetpp namespace, to allow them to be found by argument-dependent lookup via the cCommBuffer argument

// Packing/unpacking an std::vector
template<typename T, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::vector<T,A>& v)
{
    int n = v.size();
    doParsimPacking(buffer, n);
    for (int i = 0; i < n; i++)
        doParsimPacking(buffer, v[i]);
}

template<typename T, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::vector<T,A>& v)
{
    int n;
    doParsimUnpacking(buffer, n);
    v.resize(n);
    for (int i = 0; i < n; i++)
        doParsimUnpacking(buffer, v[i]);
}

// Packing/unpacking an std::list
template<typename T, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::list<T,A>& l)
{
    doParsimPacking(buffer, (int)l.size());
    for (typename std::list<T,A>::const_iterator it = l.begin(); it != l.end(); ++it)
        doParsimPacking(buffer, (T&)*it);
}

template<typename T, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::list<T,A>& l)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        l.push_back(T());
        doParsimUnpacking(buffer, l.back());
    }
}

// Packing/unpacking an std::set
template<typename T, typename Tr, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::set<T,Tr,A>& s)
{
    doParsimPacking(buffer, (int)s.size());
    for (typename std::set<T,Tr,A>::const_iterator it = s.begin(); it != s.end(); ++it)
        doParsimPacking(buffer, *it);
}

template<typename T, typename Tr, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::set<T,Tr,A>& s)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        T x;
        doParsimUnpacking(buffer, x);
        s.insert(x);
    }
}

// Packing/unpacking an std::map
template<typename K, typename V, typename Tr, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::map<K,V,Tr,A>& m)
{
    doParsimPacking(buffer, (int)m.size());
    for (typename std::map<K,V,Tr,A>::const_iterator it = m.begin(); it != m.end(); ++it) {
        doParsimPacking(buffer, it->first);
        doParsimPacking(buffer, it->second);
    }
}

template<typename K, typename V, typename Tr, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::map<K,V,Tr,A>& m)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        K k; V v;
        doParsimUnpacking(buffer, k);
        doParsimUnpacking(buffer, v);
        m[k] = v;
    }
}

// Default pack/unpack function for arrays
template<typename T>
void doParsimArrayPacking(omnetpp::cCommBuffer *b, const T *t, int n)
{
    for (int i = 0; i < n; i++)
        doParsimPacking(b, t[i]);
}

template<typename T>
void doParsimArrayUnpacking(omnetpp::cCommBuffer *b, T *t, int n)
{
    for (int i = 0; i < n; i++)
        doParsimUnpacking(b, t[i]);
}

// Default rule to prevent compiler from choosing base class' doParsimPacking() function
template<typename T>
void doParsimPacking(omnetpp::cCommBuffer *, const T& t)
{
    throw omnetpp::cRuntimeError("Parsim error: No doParsimPacking() function for type %s", omnetpp::opp_typename(typeid(t)));
}

template<typename T>
void doParsimUnpacking(omnetpp::cCommBuffer *, T& t)
{
    throw omnetpp::cRuntimeError("Parsim error: No doParsimUnpacking() function for type %s", omnetpp::opp_typename(typeid(t)));
}

}  // namespace omnetpp

namespace agrilorasec {

Register_Class(AgriSensorPacket)

AgriSensorPacket::AgriSensorPacket() : ::inet::FieldsChunk()
{
}

AgriSensorPacket::AgriSensorPacket(const AgriSensorPacket& other) : ::inet::FieldsChunk(other)
{
    copy(other);
}

AgriSensorPacket::~AgriSensorPacket()
{
}

AgriSensorPacket& AgriSensorPacket::operator=(const AgriSensorPacket& other)
{
    if (this == &other) return *this;
    ::inet::FieldsChunk::operator=(other);
    copy(other);
    return *this;
}

void AgriSensorPacket::copy(const AgriSensorPacket& other)
{
    this->temperature = other.temperature;
    this->soilHumidity = other.soilHumidity;
    this->airHumidity = other.airHumidity;
    this->nodeIndex = other.nodeIndex;
}

void AgriSensorPacket::parsimPack(omnetpp::cCommBuffer *b) const
{
    ::inet::FieldsChunk::parsimPack(b);
    doParsimPacking(b,this->temperature);
    doParsimPacking(b,this->soilHumidity);
    doParsimPacking(b,this->airHumidity);
    doParsimPacking(b,this->nodeIndex);
}

void AgriSensorPacket::parsimUnpack(omnetpp::cCommBuffer *b)
{
    ::inet::FieldsChunk::parsimUnpack(b);
    doParsimUnpacking(b,this->temperature);
    doParsimUnpacking(b,this->soilHumidity);
    doParsimUnpacking(b,this->airHumidity);
    doParsimUnpacking(b,this->nodeIndex);
}

double AgriSensorPacket::getTemperature() const
{
    return this->temperature;
}

void AgriSensorPacket::setTemperature(double temperature)
{
    handleChange();
    this->temperature = temperature;
}

double AgriSensorPacket::getSoilHumidity() const
{
    return this->soilHumidity;
}

void AgriSensorPacket::setSoilHumidity(double soilHumidity)
{
    handleChange();
    this->soilHumidity = soilHumidity;
}

double AgriSensorPacket::getAirHumidity() const
{
    return this->airHumidity;
}

void AgriSensorPacket::setAirHumidity(double airHumidity)
{
    handleChange();
    this->airHumidity = airHumidity;
}

int AgriSensorPacket::getNodeIndex() const
{
    return this->nodeIndex;
}

void AgriSensorPacket::setNodeIndex(int nodeIndex)
{
    handleChange();
    this->nodeIndex = nodeIndex;
}

class AgriSensorPacketDescriptor : public omnetpp::cClassDescriptor
{
  private:
    mutable const char **propertyNames;
    enum FieldConstants {
        FIELD_temperature,
        FIELD_soilHumidity,
        FIELD_airHumidity,
        FIELD_nodeIndex,
    };
  public:
    AgriSensorPacketDescriptor();
    virtual ~AgriSensorPacketDescriptor();

    virtual bool doesSupport(omnetpp::cObject *obj) const override;
    virtual const char **getPropertyNames() const override;
    virtual const char *getProperty(const char *propertyName) const override;
    virtual int getFieldCount() const override;
    virtual const char *getFieldName(int field) const override;
    virtual int findField(const char *fieldName) const override;
    virtual unsigned int getFieldTypeFlags(int field) const override;
    virtual const char *getFieldTypeString(int field) const override;
    virtual const char **getFieldPropertyNames(int field) const override;
    virtual const char *getFieldProperty(int field, const char *propertyName) const override;
    virtual int getFieldArraySize(omnetpp::any_ptr object, int field) const override;
    virtual void setFieldArraySize(omnetpp::any_ptr object, int field, int size) const override;

    virtual const char *getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const override;
    virtual std::string getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const override;
    virtual omnetpp::cValue getFieldValue(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const override;

    virtual const char *getFieldStructName(int field) const override;
    virtual omnetpp::any_ptr getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const override;
};

Register_ClassDescriptor(AgriSensorPacketDescriptor)

AgriSensorPacketDescriptor::AgriSensorPacketDescriptor() : omnetpp::cClassDescriptor(omnetpp::opp_typename(typeid(agrilorasec::AgriSensorPacket)), "inet::FieldsChunk")
{
    propertyNames = nullptr;
}

AgriSensorPacketDescriptor::~AgriSensorPacketDescriptor()
{
    delete[] propertyNames;
}

bool AgriSensorPacketDescriptor::doesSupport(omnetpp::cObject *obj) const
{
    return dynamic_cast<AgriSensorPacket *>(obj)!=nullptr;
}

const char **AgriSensorPacketDescriptor::getPropertyNames() const
{
    if (!propertyNames) {
        static const char *names[] = {  nullptr };
        omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
        const char **baseNames = base ? base->getPropertyNames() : nullptr;
        propertyNames = mergeLists(baseNames, names);
    }
    return propertyNames;
}

const char *AgriSensorPacketDescriptor::getProperty(const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? base->getProperty(propertyName) : nullptr;
}

int AgriSensorPacketDescriptor::getFieldCount() const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? 4+base->getFieldCount() : 4;
}

unsigned int AgriSensorPacketDescriptor::getFieldTypeFlags(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeFlags(field);
        field -= base->getFieldCount();
    }
    static unsigned int fieldTypeFlags[] = {
        FD_ISEDITABLE,    // FIELD_temperature
        FD_ISEDITABLE,    // FIELD_soilHumidity
        FD_ISEDITABLE,    // FIELD_airHumidity
        FD_ISEDITABLE,    // FIELD_nodeIndex
    };
    return (field >= 0 && field < 4) ? fieldTypeFlags[field] : 0;
}

const char *AgriSensorPacketDescriptor::getFieldName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldName(field);
        field -= base->getFieldCount();
    }
    static const char *fieldNames[] = {
        "temperature",
        "soilHumidity",
        "airHumidity",
        "nodeIndex",
    };
    return (field >= 0 && field < 4) ? fieldNames[field] : nullptr;
}

int AgriSensorPacketDescriptor::findField(const char *fieldName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    int baseIndex = base ? base->getFieldCount() : 0;
    if (strcmp(fieldName, "temperature") == 0) return baseIndex + 0;
    if (strcmp(fieldName, "soilHumidity") == 0) return baseIndex + 1;
    if (strcmp(fieldName, "airHumidity") == 0) return baseIndex + 2;
    if (strcmp(fieldName, "nodeIndex") == 0) return baseIndex + 3;
    return base ? base->findField(fieldName) : -1;
}

const char *AgriSensorPacketDescriptor::getFieldTypeString(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeString(field);
        field -= base->getFieldCount();
    }
    static const char *fieldTypeStrings[] = {
        "double",    // FIELD_temperature
        "double",    // FIELD_soilHumidity
        "double",    // FIELD_airHumidity
        "int",    // FIELD_nodeIndex
    };
    return (field >= 0 && field < 4) ? fieldTypeStrings[field] : nullptr;
}

const char **AgriSensorPacketDescriptor::getFieldPropertyNames(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldPropertyNames(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

const char *AgriSensorPacketDescriptor::getFieldProperty(int field, const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldProperty(field, propertyName);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

int AgriSensorPacketDescriptor::getFieldArraySize(omnetpp::any_ptr object, int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldArraySize(object, field);
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        default: return 0;
    }
}

void AgriSensorPacketDescriptor::setFieldArraySize(omnetpp::any_ptr object, int field, int size) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldArraySize(object, field, size);
            return;
        }
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set array size of field %d of class 'AgriSensorPacket'", field);
    }
}

const char *AgriSensorPacketDescriptor::getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldDynamicTypeString(object,field,i);
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        default: return nullptr;
    }
}

std::string AgriSensorPacketDescriptor::getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValueAsString(object,field,i);
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        case FIELD_temperature: return double2string(pp->getTemperature());
        case FIELD_soilHumidity: return double2string(pp->getSoilHumidity());
        case FIELD_airHumidity: return double2string(pp->getAirHumidity());
        case FIELD_nodeIndex: return long2string(pp->getNodeIndex());
        default: return "";
    }
}

void AgriSensorPacketDescriptor::setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValueAsString(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        case FIELD_temperature: pp->setTemperature(string2double(value)); break;
        case FIELD_soilHumidity: pp->setSoilHumidity(string2double(value)); break;
        case FIELD_airHumidity: pp->setAirHumidity(string2double(value)); break;
        case FIELD_nodeIndex: pp->setNodeIndex(string2long(value)); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'AgriSensorPacket'", field);
    }
}

omnetpp::cValue AgriSensorPacketDescriptor::getFieldValue(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValue(object,field,i);
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        case FIELD_temperature: return pp->getTemperature();
        case FIELD_soilHumidity: return pp->getSoilHumidity();
        case FIELD_airHumidity: return pp->getAirHumidity();
        case FIELD_nodeIndex: return pp->getNodeIndex();
        default: throw omnetpp::cRuntimeError("Cannot return field %d of class 'AgriSensorPacket' as cValue -- field index out of range?", field);
    }
}

void AgriSensorPacketDescriptor::setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValue(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        case FIELD_temperature: pp->setTemperature(value.doubleValue()); break;
        case FIELD_soilHumidity: pp->setSoilHumidity(value.doubleValue()); break;
        case FIELD_airHumidity: pp->setAirHumidity(value.doubleValue()); break;
        case FIELD_nodeIndex: pp->setNodeIndex(omnetpp::checked_int_cast<int>(value.intValue())); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'AgriSensorPacket'", field);
    }
}

const char *AgriSensorPacketDescriptor::getFieldStructName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructName(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    };
}

omnetpp::any_ptr AgriSensorPacketDescriptor::getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructValuePointer(object, field, i);
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        default: return omnetpp::any_ptr(nullptr);
    }
}

void AgriSensorPacketDescriptor::setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldStructValuePointer(object, field, i, ptr);
            return;
        }
        field -= base->getFieldCount();
    }
    AgriSensorPacket *pp = omnetpp::fromAnyPtr<AgriSensorPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'AgriSensorPacket'", field);
    }
}

}  // namespace agrilorasec

namespace omnetpp {

}  // namespace omnetpp

