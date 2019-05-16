import numpy as np
from http import client
import urllib.request
import re
import os, sys
import time
import threading
from tqdm import tqdm
from multiprocessing import Pool, freeze_support, RLock

class MabinogiEnvironment:
	needUpdate = False
	isDownloadable = False
	localVersion = 0
	patchVersion = 0
	ftpDomain = None
	ftpSub = None

	def __init__(self, gameDir, patchUrl):
		# version.dat의 파일 내용을 읽어온다.
		self.gameDir = str(gameDir)
		with open(os.path.join(self.gameDir, "version.dat"), 'rb') as f:
			byte = f.read()
			self.localVersion = int.from_bytes(byte, byteorder='little')

		self.InitPatchInfo(patchUrl)

		print('현재 버전: '+str(self.localVersion)+' | 최신 버전: '+str(self.patchVersion))
		
		while self.localVersion < self.patchVersion:
			if self.isDownloadable:
				print('게임 업데이트를 시작합니다.')
				self.ProcessGameUpdate(patchUrl)
				print('현재 버전: '+str(self.localVersion)+' | 최신 버전: '+str(self.patchVersion))
			else:
				print('현재 서버에서 패치 파일을 다운로드할 수 없는 상태입니다.')
				break
		
	def InitPatchInfo(self, patchUrl):
		patchUrl = re.sub(r'^(ht|f)tp(s?)\:\/\/', '', patchUrl).split('/', 1) # 두 개의 값만 나와야 한다, 두번째 인수에 최대 인덱스가 될 1 을 넣어줘야 한다.
		patchUrlDomain = patchUrl[0]
		patchUrlSub = '/' + patchUrl[1]

		connection = client.HTTPConnection(patchUrlDomain)
		connection.request('GET', patchUrlSub)

		response = connection.getresponse()
		responseBody = response.read().decode('utf-8')

		patchText = responseBody.split('\r\n')

		patchInfo = {}
		for s in patchText:
			ss = s.split('=', 1)
			patchInfo[ss[0]] = ss[1]

		''' 
{'patch_accept': '1', 'local_version': '1033', 'local_ftp': 'mabi.dn.nexoncdn.co.kr:80/patch/', 'main_version': '1033', 'main_ftp': 'mabi.dn.nexoncdn.co.kr:80/patch/', 'launcherinfo': '190', 'login': '211.218.233.101', 'arg': 'chatip:211.218.233.193 chatport:8002 resourcesvr:"http://mabi.dn.nexoncdn.co.kr/data/" setting:"file://data/features.xml=Regular, Korea"   lang=patch_langpack.txt', 'addin': '193 addin.txt', 'main_fullversion': '997', 'local_fullversion': '997', 'dumpip': '211.218.233.28:9999', 'st_dt': '20180719045000', 'ed_dt': '20180719120000'}
		'''

		self.isDownloadable = True if patchInfo['patch_accept'] == '1' else False
		self.patchVersion = int(patchInfo['patch_version'])
		ftpUrl = patchInfo['ftp'].split('/', 1)
		self.ftpDomain = ftpUrl[0]
		self.ftpSub = '/' + ftpUrl[1]

	def ProcessGameUpdate(self, patchUrl):
		currentGoalVersion = self.patchVersion
		self.ProcessUpdatePackages(currentGoalVersion)
		self.localVersion = currentGoalVersion
		self.ValidateVersionFile(self.localVersion)
	
	def ProcessUpdatePackages(self, goalVersion):
		print('게임 파일 패치 다운로드를 진행합니다.')

		connection = client.HTTPConnection(self.ftpDomain)
		# http://mabi.dn.nexoncdn.co.kr/patch/1/version.txt
		connection.request('GET', self.ftpSub+str(goalVersion)+'/version.txt')
		response = connection.getresponse()
		
		if response.status == 404:
			print('패키지를 다운로드 하는 도중 문제가 발생했습니다.')
			print('문제가 계속되면 홈페이지에서 게임을 업데이트해주세요.')
			input()
			sys.exit()
	
		responseBody = response.read().decode('utf-8')

		# 업데이트에 필요한 파일 정보만 리스트로 추출
		#packageList = [p for p in responseBody.split('\r\n') if p.find(str(self.localVersion)+'_to_'+str(goalVersion)) != -1 or p.find('language') != -1]
		
		packageList = [p for p in responseBody.split('\r\n')]
		if len(packageList[-1]) == 0:
			del packageList[-1] #마지막 빈 줄 제거
		packageList = [tuple(f.split('\t')) for f in packageList if int(f.split('\t')[3]) > self.localVersion]

		self.downloadedCount = 0

		freeze_support()  # for Windows support
		p = Pool(processes=5,
             # again, for Windows support
             initializer=tqdm.set_lock, initargs=(RLock(),))
		p.map(self.DownloadFile, enumerate(packageList))
		print("\n" * (len(packageList) - 2))
		p.close()
		p.join()

		os.system('cls')
			#urllib.request.urlretrieve('http://'+self.ftpDomain+self.ftpSub+'Mabinogi/'+fileInfo[0], os.path.join(self.gameDir, fileInfo[0]), show_progress)
			# 추후에 추가 할 해쉬 검증 과정,
			# 여기에 해쉬 검증 과정 분기문을 두고,

			# 해쉬 검증 성공 시 다음으로 진행
			# 해쉬 검증 실패 시 while문을 이용해 성공할 때 까지 다운로드하도록 함
	def DownloadFile(self, packageInfo):
		index = packageInfo[0]
		packageInfo = packageInfo[1]
		url = 'http://%s%sMabinogi/%s' % (self.ftpDomain, self.ftpSub, packageInfo[0])
		dest = os.path.join(self.gameDir, packageInfo[0])
		desc = (url.split('/')[-1])
		with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1, desc=desc, position=index%2, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as t:  # all optional kwargs
			local_filename, headers = urllib.request.urlretrieve(url, filename=dest, reporthook=t.update_to, data=None)
			if local_filename:
				self.downloadedCount += 1
		
	# version.dat 파일의 내용을 수정한다.
	def ValidateVersionFile(self, version):
		with open(os.path.join(self.gameDir, "version.dat"), 'wb') as f:
		#	byte = version.to_bytes((version.bit_length() + 7) // 8, byteorder='little')
			word_length = (version.bit_length() // 4) + (1 if version.bit_length() % 4 > 0 else 0)
			# word_length + (4 - (word_length % 4)) 는 word 길이를 가지고 pad된 word사이즈의 bit길이를 뽑아낸다. 
			byte = version.to_bytes(word_length + (4 - (word_length % 4)), byteorder='little')
			f.write(byte)

class TqdmUpTo(tqdm):
	def update_to(self, b=1, bsize=1, tsize=None):
		"""
		b  : int, optional
			Number of blocks transferred so far [default: 1].
		bsize  : int, optional
			Size of each block (in tqdm units) [default: 1].
		tsize  : int, optional
			Total size (in tqdm units). If [default: None] remains unchanged.
		"""
		if tsize is not None:
			self.total = tsize
		self.update(b * bsize - self.n)  # will also set self.n = b * bsize
