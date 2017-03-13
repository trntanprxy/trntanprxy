#!/usr/bin/env python
# -*- coding: utf-8 -*- 

# GAE-based webproxy server. V.6
# License: CC0 1.0
# 
# To the extent possible under law, the person who associated CC0 with
# app has waived all copyright and related or neighboring rights
# to app.

# -----------------------------------------------------------------------------
#
# Изменив параметры ниже вы можете перенастроить 
# ваш проксисервер на работу с другим узлом
#
# -----------------------------------------------------------------------------
# Введите здесь имя хоста. Его страницы будет транслировать проксисервер.
# Например: "kinozal.tv"

host_name = "rutracker.org"

# -----------------------------------------------------------------------------
# Тип соединения с указанным выше хостом.
# Допустимы только значения "http" или "https".

host_scheme = "http"

# -----------------------------------------------------------------------------
# Включает/выключает использование защищенного соединения с проксисервером. 
# Если страницы хоста открываются с ошибками или не работает авторизация 
# попробуйте выключить (0) эту опцию.
# Допустимы значения 0 или 1 (без кавычек).

encrypted_connection = 0

# -----------------------------------------------------------------------------

import webapp2
import logging
import re
from google.appengine.api import urlfetch

class MainHandler(webapp2.RequestHandler):
  def head(self):    self.get()
  def post(self):    self.get()
  def put(self):     self.get()
  def patch(self):   self.get()
  def delete(self):  self.get()
  def trace(self):   self.get()
  def connect(self): self.get()
  
  def get(self):
    
    # force on/off encrypted connection to the proxy
    url_tail = self.request.host + self.request.path_qs
    
    if encrypted_connection and 'https' != self.request.scheme:
      self.response.set_status(301)
      self.response.headers['Location'] = 'https://' + url_tail
      return
    
    if not encrypted_connection and 'http' != self.request.scheme:
      self.response.set_status(301)
      self.response.headers['Location'] = 'http://' + url_tail
      return
    
    # decode name of subdomain
    if encrypted_connection:
      self.proxy_host = self.request.host
      a = self.request.path_qs.split('/', 2)
      subdomain = ''
    
      if len(a[1]) > 2 and '.' == a[1][0]:
        subdomain = a[1][1:]
        a = a[1:]
        a[0] = ''
      
      path_qs = '/'.join(a)
    
    else:
      a = self.request.host.split('.')
      self.proxy_host = '.'.join(a[-3:])
      a = a[0:-2]
      
      if len(a) > 1 and re.match('^\d+$', a[-2]):
        self.proxy_host = a[-2] + '.' + self.proxy_host
        a = a[0:-1]
      
      a[-1] = ''
      subdomain = '.'.join(a)
      path_qs = self.request.path_qs
      
    url = host_scheme + '://' + subdomain + host_name + path_qs
    logging.info(url)
    
    # translate browser headers
    headers = {}
    
    for name, value in self.request.headers.iteritems():
      if 'X' != name[0]:
        value = value.replace(self.proxy_host, host_name)
        headers[name] = value 
    
    # send req to host
    rpc = urlfetch.create_rpc(deadline = 20)
    rpc.callback = lambda: self.output_result(rpc)
    
    urlfetch.make_fetch_call(
        rpc              = rpc, 
        url              = url,
        payload          = self.request.body,
        method           = self.request.method,
        headers          = headers,
        allow_truncated  = False,
        follow_redirects = False
    )
    try:
      rpc.wait()
    except Exception as e:
      self.response.set_status(404)
      self.response.write(str(e))
      logging.error(str(e))
  
  
  def output_result(self, rpc):
    result = rpc.get_result()
    content = result.content
    
    # headers of response
    self.response.set_status(result.status_code)
    self.response.headers = {}
    c_type  = '??'
    
    for h_line in re.split('[\n\r]+', str(result.header_msg)):
      a = h_line.split(':', 1)
      
      if len(a) > 1: 
        name  = a[0].strip()
        value = a[1].strip().replace(host_name, self.proxy_host)
        self.response.headers.add_header(name, value)
        
        if 'content-type' == name.lower():
          c_type = re.split('[:; \/\\\\=]+', value.lower())
        
    # update text content
    if c_type[0] in ['text', 'application'] and \
       c_type[1] in ['html', 'xml', 'xhtml+xml', 'css', 'javascript']:
      
      def dashrepl(matchobj):
        s = self.request.scheme + '://'
        
        if encrypted_connection:
          s += self.proxy_host
          if matchobj.group(3): s += '/.' + matchobj.group(3) 
      
        else:
          if matchobj.group(3): s += matchobj.group(3) 
          s += self.proxy_host
          
        return s;
    
      regexp = '(?<=[^:])(http:|https:)(\/\/)([-\.a-z0-9]+\.|)'
      regexp += re.escape(host_name)
      content = re.sub(regexp, dashrepl, content, flags = re.IGNORECASE)
    
    self.response.out.write(content)

app = webapp2.WSGIApplication([
    ('/.*', MainHandler)
], debug=True)
