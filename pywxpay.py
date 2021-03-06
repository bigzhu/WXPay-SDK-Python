# coding: utf-8
# wxpay sdk

import hashlib
import copy
import uuid
import requests
import sys
import xmltodict


try:
    reload(sys)
    sys.setdefaultencoding('utf-8')
except:
    pass

PY2 = sys.version_info[0] == 2
if not PY2:
    # Python 3.x and up
    text_type = str
    string_types = (str,)
    xrange = range

    def as_text(v):  ## 生成unicode字符串
        if v is None:
            return None
        elif isinstance(v, bytes):
            return v.decode('utf-8', errors='ignore')
        elif isinstance(v, str):
            return v
        else:
            raise ValueError('Unknown type %r' % type(v))

    def is_text(v):
        return isinstance(v, text_type)

else:
    # Python 2.x
    text_type    = unicode
    string_types = (str, unicode)
    xrange       = xrange

    def as_text(v):
        if v is None:
            return None
        elif isinstance(v, unicode):
            return v
        elif isinstance(v, str):
            return v.decode('utf-8', errors='ignore')
        else:
            raise ValueError('Invalid type %r' % type(v))

    def is_text(v):
        return isinstance(v, text_type)


_SIGN = 'sign'
_FAIL = 'FAIL'
_SUCCESS = 'SUCCESS'

_DEFAULT_TIMEOUT = 6000  # 微秒
_MICROPAY_URL = 'https://api.mch.weixin.qq.com/pay/micropay'
_UNIFIEDORDER_URL = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
_ORDERQUERY_URL = 'https://api.mch.weixin.qq.com/pay/orderquery'
_REVERSE_URL = 'https://api.mch.weixin.qq.com/secapi/pay/reverse'
_CLOSEORDER_URL = 'https://api.mch.weixin.qq.com/pay/closeorder'
_REFUND_URL = 'https://api.mch.weixin.qq.com/secapi/pay/refund'
_REFUNDQUERY_URL = 'https://api.mch.weixin.qq.com/pay/refundquery'
_DOWNLOADBILL_URL = 'https://api.mch.weixin.qq.com/pay/downloadbill'
_REPORT_URL = 'https://api.mch.weixin.qq.com/pay/report'
_SHORTURL_URL = 'https://api.mch.weixin.qq.com/tools/shorturl'
_AUTHCODETOOPENID_URL = 'https://api.mch.weixin.qq.com/tools/authcodetoopenid'


class WXPayUtil(object):

    @staticmethod
    def dict2xml(data_dict):
        """ dict to xml"""
        return as_text( xmltodict.unparse({'xml': data_dict}, pretty=True) )

    @staticmethod
    def xml2dict(xml_str):
        """ xml to dict """
        return xmltodict.parse(xml_str)['xml']

    @staticmethod
    def generate_signature(data_dict, key_str):
        """ 生成签名 """
        key_str = as_text(key_str)
        data_key_list = data_dict.keys()
        data_key_list = sorted(data_key_list)  # 排序！
        combine_str = as_text('')
        for k in data_key_list:
            v = data_dict[k]
            if _SIGN == k:
                continue
            if v is None or len(str(v)) == 0:
                continue
            combine_str = combine_str + as_text(str(k)) + as_text('=') + as_text(str(v)) + as_text('&')
        combine_str = combine_str + as_text('key=') + key_str
        hash_md5 = hashlib.md5(combine_str.encode('utf-8'))
        return hash_md5.hexdigest().upper()

    @staticmethod
    def is_signature_valid(xml_data, key_str):
        """
        验证xml中的签名
        :param xml_data: xml格式的字符串，或者dict类型
        :param key_str: 微信支付的KEY，用于签名
        :return:
        """
        key_str = as_text(key_str)
        if isinstance(xml_data, dict):
            data_dict = xml_data
        else:
            data_dict = WXPayUtil.xml2dict(as_text(xml_data))
        if _SIGN not in data_dict:
            return False
        sign = WXPayUtil.generate_signature(data_dict, key_str)
        if sign == data_dict[_SIGN]:
            return True
        return False

    @staticmethod
    def generate_signed_xml(data_dict, key_str):
        """ 生成带有签名的xml """
        key_str = as_text(key_str)
        new_data_dict = copy.deepcopy(data_dict)
        sign = WXPayUtil.generate_signature(data_dict, key_str)
        new_data_dict[_SIGN] = sign
        return WXPayUtil.dict2xml( new_data_dict )

    @staticmethod
    def generate_nonce_str():
        """ 随机字符串 """
        r = uuid.uuid1().hex.replace('-', '')
        return as_text(r)


class SignInvalidException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class WXPay(object):

    def __init__(self, app_id, mch_id, sub_mch_id, key, cert_pem_path, key_pem_path, timeout=_DEFAULT_TIMEOUT):
        """
        timeout: 网络请求超时时间，单位毫秒
        """
        self.app_id = app_id
        self.mch_id = mch_id
        self.sub_mch_id = sub_mch_id
        self.key = key
        self.cert_pem_path = cert_pem_path
        self.key_pem_path = key_pem_path
        self.timeout = timeout

    def _process_response_xml(self, resp_xml):
        """
        处理微信支付返回的 xml 格式数据
        :param resp_xml:
        :return:
        """
        resp_dict = WXPayUtil.xml2dict(resp_xml)
        if 'return_code' in resp_dict:
            return_code = resp_dict.get('return_code')
        else:
            raise Exception('no return_code in response data: {}'.format(resp_xml))

        if return_code == _FAIL:
            return resp_dict
        elif return_code == _SUCCESS:
            if self.is_signature_valid(resp_dict):
                return resp_dict
            else:
                raise SignInvalidException('invalid sign of response data: {}'.format(resp_xml))
        else:
            raise Exception('return_code value {} is invalid of response data: {}'.format(return_code, resp_xml))

    def micropay(self, data_dict, timeout=None):
        """
        作用：提交刷卡支付
        场景：刷卡支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_MICROPAY_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def unifiedorder(self, data_dict, timeout=None):
        """
        作用：统一下单
        场景：公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_UNIFIEDORDER_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def orderquery(self, data_dict, timeout=None):
        """
        作用：查询订单
        场景：刷卡支付、公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_ORDERQUERY_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def reverse(self, data_dict, timeout=None):
        """
        作用：撤销订单
        场景：刷卡支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_with_cert(_REVERSE_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def closeorder(self, data_dict, timeout=None):
        """
        作用：关闭订单
        场景：公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_CLOSEORDER_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def refund(self, data_dict, timeout=None):
        """
        作用：申请退款
        场景：刷卡支付、公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_with_cert(_REFUND_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def refundquery(self, data_dict, timeout=None):
        """
        作用：退款查询
        场景：刷卡支付、公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_REFUNDQUERY_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def downloadbill(self, data_dict, timeout=None):
        """
        作用：对账单下载（成功时返回对账单数据，失败时返回XML格式数据）
        场景：刷卡支付、公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp = self.request_without_cert(_DOWNLOADBILL_URL, data_dict, _timeout).strip()
        if resp.startswith('<'): # 是xml，下载出错了
            resp_dict = WXPayUtil.xml2dict(resp)
        else:  # 下载成功，加一层封装
            resp_dict = {'return_code': 'SUCCESS', 'return_msg': '', 'data': resp}
        return resp_dict

    def report(self, data_dict, timeout=None):
        """
        作用：交易保障
        场景：刷卡支付、公共号支付、扫码支付、APP支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_REPORT_URL, data_dict, _timeout)
        resp_dict = WXPayUtil.xml2dict(resp_xml)
        return resp_dict

    def shorturl(self, data_dict, timeout=None):
        """
        作用：转换短链接
        场景：刷卡支付、扫码支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_SHORTURL_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def authcodetoopenid(self, data_dict, timeout=None):
        """
        作用：授权码查询OPENID接口
        场景：刷卡支付
        """
        _timeout = self.timeout if timeout is None else timeout
        resp_xml = self.request_without_cert(_AUTHCODETOOPENID_URL, data_dict, _timeout)
        return self._process_response_xml(resp_xml)

    def is_signature_valid(self, xml_data):
        """
        检查xml中签名是否合法
        :param xml_data: xml格式的字符串、或者dict类型
        :return:
        """
        return WXPayUtil.is_signature_valid(xml_data, self.key)

    def make_request_body(self, data_dict):
        """ 生成请求体 """
        new_data_dict = copy.deepcopy(data_dict)
        new_data_dict['appid'] = self.app_id
        new_data_dict['mch_id'] = self.mch_id
        new_data_dict['sub_mch_id'] = self.sub_mch_id
        new_data_dict['nonce_str'] = WXPayUtil.generate_nonce_str()
        return WXPayUtil.generate_signed_xml(new_data_dict, self.key)

    def request_with_cert(self, url_str, data_dict, timeout=None):
        """ """
        req_body = self.make_request_body(data_dict).encode('utf-8')
        req_headers = {'Content-Type': 'application/xml'}
        _timeout = self.timeout if timeout is None else timeout
        resp = requests.post(url_str,
                            data=req_body,
                            headers=req_headers,
                            timeout=_timeout/1000.0,
                            cert=(self.cert_pem_path, self.key_pem_path),
                            verify=True)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            # print as_text(resp.text)
            return as_text(resp.text)
        raise Exception('HTTP response code is not 200')

    def request_without_cert(self, url_str, data_dict, timeout=None):
        """ """
        req_body = self.make_request_body(data_dict).encode('utf-8')
        req_headers = {'Content-Type': 'application/xml'}
        _timeout = self.timeout if timeout is None else timeout
        resp = requests.post(url_str,
                             data=req_body,
                             headers=req_headers,
                             timeout=_timeout/1000.0)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            # print as_text(resp.text)
            return as_text(resp.text)
        raise Exception('HTTP response code is not 200')
