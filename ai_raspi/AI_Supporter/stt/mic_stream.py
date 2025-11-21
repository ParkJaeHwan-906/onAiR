import sounddevice as sd
import numpy as np
import queue
from scipy import signal
from config import settings


class MicStream:
    def __init__(self):
        self.mic_rate = settings.MIC_RATE  # 마이크 실제 샘플레이트 (48000Hz)
        self.stt_rate = settings.RATE       # STT용 샘플레이트 (16000Hz)
        self.rate = self.stt_rate           # 호환성을 위한 속성 (GCP STT는 16000Hz 기대)
        self.chunk = int(self.mic_rate * settings.CHUNK_MS / 1000)
        self.channels = settings.CHANNELS
        self.device_index = settings.DEVICE_INDEX
        self.q = queue.Queue()
        self.stream = None
        self.is_paused = False
        self.wakeword_callback = None  # Wakeword 감지기 콜백
        self._fallback_devices = []  # 장치 열기 실패 시 시도할 대체 장치 목록

    def set_wakeword_callback(self, callback):
        """Wakeword 감지기 콜백 설정 (16000Hz 오디오 데이터를 받음)"""
        self.wakeword_callback = callback
    
    def disable_wakeword_callback(self):
        """Wakeword 콜백 비활성화 (STT 세션 중 wakeword 감지 중지)"""
        self.wakeword_callback = None
    
    def enable_wakeword_callback(self, callback):
        """Wakeword 콜백 활성화 (STT 세션 종료 후 wakeword 감지 재개)"""
        self.wakeword_callback = callback

    def _callback(self, in_data, frames, time_info, status):
        """입력 오디오 데이터를 큐에 저장 및 Wakeword 감지기에 전달"""
        if not self.is_paused:
            self.q.put(in_data.copy())
            
            # Wakeword 감지기에 오디오 데이터 전달 (16000Hz로 리샘플링)
            if self.wakeword_callback is not None:
                audio_48k = np.frombuffer(in_data, dtype=np.int16)
                # 48000Hz → 16000Hz 리샘플링
                if self.mic_rate != self.stt_rate:
                    num_samples_16k = int(len(audio_48k) * self.stt_rate / self.mic_rate)
                    audio_16k = signal.resample(audio_48k.astype(np.float32), num_samples_16k)
                    audio_16k_int = audio_16k.astype(np.int16)
                else:
                    audio_16k_int = audio_48k
                
                # Wakeword 감지기 콜백 호출
                try:
                    self.wakeword_callback(audio_16k_int)
                except Exception as e:
                    # Wakeword 감지기 오류는 무시 (메인 스트림에 영향 없음)
                    pass

    def start(self):
        """마이크 스트림 시작 (마이크는 실제 샘플레이트로 열기)"""
        # 마이크 장치 선택
        device = self.device_index
        
        # ALSA 호스트 API 찾기
        alsa_hostapi = None
        try:
            hostapis = sd.query_hostapis()
            # [25.11.21] 로그 주석 처리 - 재환 
            # print("🔍 사용 가능한 호스트 API:")
            for idx, api in enumerate(hostapis):
                api_name = api.get('name', 'Unknown')
                api_index = api.get('index', idx)
                # [25.11.21] 로그 주석 처리 - 재환
                # print(f"   [{api_index}] {api_name}")
                if 'ALSA' in api_name or 'alsa' in api_name.lower():
                    alsa_hostapi = api_index
                    # [25.11.21] 로그 주석 처리 - 재환
                    # print(f"✅ ALSA 호스트 API 발견: {api_name} (인덱스: {alsa_hostapi})")
                    break
            # [25.11.21] 로그 주석 처리 - 재환
            # if alsa_hostapi is None:
            #     print("⚠️ ALSA 호스트 API를 찾을 수 없습니다.")
        except Exception as e:
            # [25.11.21] 로그 주석 처리 - 재환
            # print(f"⚠️ 호스트 API 조회 실패: {e}")
            import traceback
            traceback.print_exc()
        
        # ALSA 장치 이름 문자열인 경우 (예: 'hw:0,0')
        # sounddevice는 ALSA 장치 이름 문자열을 직접 지원하지 않으므로 장치 인덱스로 변환 시도
        if isinstance(device, str):
            # [25.11.21] 로그 주석 처리 - 재환
            # print(f"🔍 ALSA 장치 이름 사용: {device}")
            # print(f"   ⚠️ sounddevice는 ALSA 장치 이름 문자열을 직접 지원하지 않습니다.")
            # print(f"   💡 ALSA 레벨에서 실제 입력 장치를 확인하세요:")
            # print(f"      $ arecord -l")
            # print(f"      $ python3.10 check_alsa_devices.py")
            
            # 장치 이름으로 검색 시도
            all_devices = sd.query_devices()
            device_found = None
            for idx, dev in enumerate(all_devices):
                if device in dev['name'] or dev['name'] in device:
                    # 장치 이름이 일치하지만 입력 채널이 있어야 함
                    if dev['max_input_channels'] > 0:
                        device_found = idx
                        # [25.11.21] 로그 주석 처리 - 재환
                        # print(f"✅ 장치 이름으로 입력 장치 찾음: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']})")
                        break
            
            if device_found is not None:
                device = device_found
            else:
                # [25.11.21] 로그 주석 처리 - 재환
                # print(f"⚠️ 장치 이름 '{device}'으로 입력 장치를 찾을 수 없음")
                device = None
        elif device is None:
            # 기본 입력 장치 자동 선택
            try:
                # [25.11.21] 로그 주석 처리 - 재환
                # print("🔍 마이크 장치 자동 검색 중...")

                all_devices = sd.query_devices()
                
                # [25.11.21] 로그 주석 처리 - 재환
                # print(f"   전체 장치 수: {len(all_devices)}")
                
                # ALSA 호스트 API가 있으면 ALSA 장치만 검색
                if alsa_hostapi is not None:
                    # [25.11.21] 로그 주석 처리 - 재환
                    # print(f"   ALSA 호스트 API 사용 (인덱스: {alsa_hostapi})")

                    # ALSA 호스트 API의 모든 장치를 수집 (입력 채널이 0이어도 포함)
                    # query_devices가 잘못된 정보를 반환할 수 있으므로 모든 장치를 시도
                    alsa_devices = []
                    for idx, dev in enumerate(all_devices):
                        dev_hostapi = dev.get('hostapi', None)
                        if dev_hostapi == alsa_hostapi:
                            alsa_devices.append((idx, dev))
                            # [25.11.21] 로그 주석 처리 - 재환
                            # if dev['max_input_channels'] > 0:
                            #     print(f"      발견: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz)")
                            # else:
                            #     print(f"      후보: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 실제 확인 필요)")
                    
                    # 입력 채널이 있는 장치를 우선순위로, 없으면 모든 장치를 시도
                    input_devices_found = [d for d in alsa_devices if d[1]['max_input_channels'] > 0]
                    if not input_devices_found:
                        # 입력 채널이 0으로 보고되더라도 ALSA 장치는 모두 시도
                        input_devices_found = alsa_devices
                    
                    if input_devices_found:
                        # 첫 번째 장치를 선택 (실제로 열어보고 실패하면 다음 장치 시도)
                        device = input_devices_found[0][0]
                        dev_name = input_devices_found[0][1]['name']
                        print(f"✅ ALSA 입력 장치 선택: {dev_name} (인덱스: {device})")
                        # 여러 장치가 있으면 나중에 시도할 수 있도록 저장
                        if len(input_devices_found) > 1:
                            self._fallback_devices = [d[0] for d in input_devices_found[1:]]
                        else:
                            self._fallback_devices = []
                    else:
                        print("⚠️ ALSA 호스트 API에서 장치를 찾을 수 없음")
                        print("   💡 ALSA 레벨에서 마이크 확인:")
                        print("      $ arecord -l")
                        print("      $ python3.10 check_alsa_devices.py")
                        # 일반 검색으로 fallback
                        input_devices = [dev for dev in all_devices if dev['max_input_channels'] > 0]
                        print(f"   입력 장치 수 (수동 필터링): {len(input_devices)}")
                        self._fallback_devices = []
                else:
                    # ALSA 호스트 API가 없으면 일반 검색
                    # 입력 장치만 필터링 (kind='input' 사용)
                    try:
                        input_devices = sd.query_devices(kind='input')
                        print(f"   입력 장치 수: {len(input_devices)}")
                    except Exception:
                        # kind='input'이 지원되지 않는 경우 수동 필터링
                        input_devices = [dev for dev in all_devices if dev['max_input_channels'] > 0]
                        print(f"   입력 장치 수 (수동 필터링): {len(input_devices)}")
                
                # 기본 입력 장치 인덱스 가져오기
                try:
                    default_device = sd.default.device
                    # _InputOutputPair 객체 처리
                    if hasattr(default_device, 'input'):
                        default_input_idx = default_device.input
                    elif hasattr(default_device, '__getitem__'):
                        try:
                            default_input_idx = default_device[0]
                            # _InputOutputPair 객체인 경우 .input 속성 확인
                            if hasattr(default_input_idx, 'input'):
                                default_input_idx = default_input_idx.input
                        except (TypeError, IndexError):
                            default_input_idx = None
                    else:
                        default_input_idx = None
                    
                    # 정수인지 확인
                    if isinstance(default_input_idx, int) and default_input_idx >= 0:
                        # 기본 입력 장치가 유효한지 확인
                        if default_input_idx < len(all_devices):
                            default_input = all_devices[default_input_idx]
                            if default_input['max_input_channels'] > 0:
                                device = default_input_idx
                                print(f"✅ 기본 입력 장치 자동 선택: {default_input['name']} (인덱스: {device})")
                            else:
                                print(f"⚠️ 기본 입력 장치 [{default_input_idx}]는 입력 채널이 없습니다.")
                                raise ValueError("기본 입력 장치가 입력을 지원하지 않음")
                        else:
                            print(f"⚠️ 기본 입력 장치 인덱스 [{default_input_idx}]가 범위를 벗어남")
                            raise ValueError("기본 입력 장치 인덱스가 유효하지 않음")
                    else:
                        print(f"⚠️ 기본 입력 장치가 설정되지 않음 (인덱스: {default_input_idx}, 타입: {type(default_input_idx)})")
                        raise ValueError("기본 입력 장치가 설정되지 않음")
                except (AttributeError, ValueError, IndexError, TypeError) as e:
                    print(f"⚠️ 기본 장치 선택 실패: {e}")
                    # 기본 장치를 찾을 수 없으면 입력 가능한 첫 번째 장치 선택
                    # (ALSA 호스트 API를 사용한 검색에서 이미 device가 설정되었으면 건너뜀)
                    if device is None:
                        print("   입력 가능한 장치 검색 중...")
                        input_devices_found = []
                        
                        # 입력 장치 목록에서 찾기
                        for input_dev in input_devices:
                            # 전체 장치 목록에서 인덱스 찾기
                            for idx, dev in enumerate(all_devices):
                                if dev['name'] == input_dev['name'] and dev['max_input_channels'] > 0:
                                    input_devices_found.append((idx, dev))
                                    print(f"      발견: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz)")
                                    break
                        
                        # 입력 장치 목록이 비어있으면 전체 장치에서 다시 검색
                        if not input_devices_found:
                            for idx, dev in enumerate(all_devices):
                                if dev['max_input_channels'] > 0:
                                    input_devices_found.append((idx, dev))
                                    print(f"      발견: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz)")
                        
                        if input_devices_found:
                            # 첫 번째 입력 장치 선택
                            device = input_devices_found[0][0]
                            dev_name = input_devices_found[0][1]['name']
                            print(f"✅ 입력 가능한 장치 선택: {dev_name} (인덱스: {device})")
                        else:
                            raise RuntimeError("입력 가능한 마이크 장치를 찾을 수 없습니다.")
            except Exception as e:
                print(f"⚠️ 마이크 장치 자동 선택 실패: {e}")
                print("   사용 가능한 장치 목록:")
                try:
                    devices = sd.query_devices()
                    if len(devices) == 0:
                        print("      ❌ 장치가 하나도 없습니다!")
                    else:
                        input_found = False
                        for idx, dev in enumerate(devices):
                            is_input = dev['max_input_channels'] > 0
                            is_output = dev['max_output_channels'] > 0
                            device_type = []
                            if is_input:
                                device_type.append("입력")
                            if is_output:
                                device_type.append("출력")
                            
                            marker = ""
                            try:
                                default_device = sd.default.device
                                if hasattr(default_device, 'input'):
                                    default_input_idx = default_device.input
                                elif hasattr(default_device, '__getitem__'):
                                    try:
                                        default_input_idx = default_device[0]
                                        if hasattr(default_input_idx, 'input'):
                                            default_input_idx = default_input_idx.input
                                    except (TypeError, IndexError):
                                        default_input_idx = None
                                else:
                                    default_input_idx = None
                                
                                if isinstance(default_input_idx, int) and idx == default_input_idx:
                                    marker = " [기본 입력]"
                            except:
                                pass
                            
                            print(f"      [{idx}] {dev['name']}")
                            print(f"          타입: {', '.join(device_type) if device_type else '없음'}")
                            print(f"          입력 채널: {dev['max_input_channels']}, 출력 채널: {dev['max_output_channels']}")
                            print(f"          샘플레이트: {dev['default_samplerate']}Hz{marker}")
                            
                            if is_input:
                                input_found = True
                        
                        if not input_found:
                            print("      ❌ 입력 가능한 장치가 없습니다!")
                            print()
                            print("   문제 해결 방법:")
                            print("   1. ALSA 레벨에서 마이크 확인:")
                            print("      $ python3.10 check_alsa_devices.py")
                            print("      $ arecord -l")
                            print("   2. ALSA 장치 이름을 직접 사용:")
                            print("      config/settings.py에서 DEVICE_INDEX = 'hw:0,0' 설정")
                            print("      (arecord -l 결과에서 확인한 장치 이름 사용)")
                            print("   4. 마이크가 연결되어 있는지 확인")
                            print("   5. 권한 확인: $ sudo usermod -a -G audio $USER")
                            print("   6. 재로그인 후 다시 시도")
                except Exception as debug_e:
                    print(f"      ❌ 장치 목록 조회 실패: {debug_e}")
                
                print()
                print("   💡 ALSA 장치 이름을 직접 사용할 수 있습니다:")
                print("      config/settings.py에서 DEVICE_INDEX = 'hw:0,0' 설정")
                print("      (arecord -l 결과에서 확인한 장치 이름 사용)")
                print()
                raise RuntimeError(f"마이크 장치를 찾을 수 없습니다. config/settings.py에서 DEVICE_INDEX를 설정하거나 ALSA 장치 이름을 사용하세요.")
        
        try:
            # ALSA 호스트 API를 직접 사용하여 마이크 접근 시도
            stream_kwargs = {
                'samplerate': self.mic_rate,  # 마이크 실제 샘플레이트 사용
                'channels': self.channels,
                'dtype': 'int16',
                'callback': self._callback,
                'blocksize': self.chunk,
            }
            
            # ALSA 호스트 API 사용 (이미 위에서 찾았으므로 재사용)
            try:
                if alsa_hostapi is not None:
                    # ALSA 호스트 API를 사용하여 장치 열기
                    # device가 None이면 ALSA의 기본 입력 장치 사용
                    if device is None:
                        # ALSA 호스트 API의 입력 장치 찾기
                        all_devices = sd.query_devices()
                        device_idx = None
                        for idx, dev in enumerate(all_devices):
                            # hostapi 속성이 있는지 확인하고 ALSA 호스트 API인지 확인
                            dev_hostapi = dev.get('hostapi', None)
                            if dev_hostapi == alsa_hostapi and dev['max_input_channels'] > 0:
                                device_idx = idx
                                print(f"✅ ALSA 입력 장치 찾음: [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']})")
                                break
                        
                        if device_idx is not None:
                            stream_kwargs['device'] = device_idx
                        else:
                            print("⚠️ ALSA 호스트 API에서 입력 장치를 찾을 수 없음")
                            print("   💡 실제 입력 장치를 확인하세요:")
                            print("      $ arecord -l")
                            print("      $ python3.10 check_alsa_devices.py")
                            # 입력 채널이 0인 장치는 사용하지 않음 (채널 오류 방지)
                            stream_kwargs['device'] = device
                    else:
                        stream_kwargs['device'] = device
                else:
                    print("⚠️ ALSA 호스트 API를 찾을 수 없음, 기본 설정 사용")
                    stream_kwargs['device'] = device
            except Exception as e:
                print(f"⚠️ ALSA 호스트 API 확인 실패: {e}, 기본 설정 사용")
                stream_kwargs['device'] = device
            
            # 입력 채널이 0인 장치도 실제로 열어보고 확인
            # query_devices가 잘못된 정보를 반환할 수 있으므로 실제로 열어보는 것이 중요
            if stream_kwargs.get('device') is not None:
                try:
                    device_info = sd.query_devices(stream_kwargs['device'])
                    if device_info['max_input_channels'] == 0:
                        # 입력 채널이 0으로 보고되더라도 실제로 열 수 있는지 확인
                        # hw:0,0 같은 ALSA 장치는 입력 채널이 있지만 query_devices가 잘못 보고할 수 있음
                        if 'hw:' in device_info['name'] or 'plughw:' in device_info['name'] or 'googlevoicehat' in device_info['name'].lower():
                            print(f"⚠️ 장치 [{stream_kwargs['device']}] {device_info['name']}는 입력 채널이 0으로 보고되지만 실제로 열어보겠습니다.")
                        else:
                            raise RuntimeError(f"장치 [{stream_kwargs['device']}] {device_info['name']}는 입력 채널이 0개입니다. 입력 장치를 사용하세요.")
                except (KeyError, IndexError, TypeError):
                    pass  # 장치 정보를 가져올 수 없으면 그냥 시도
            
            # 실제로 장치를 열어보고 입력 채널이 있는지 확인
            # 여러 장치를 시도할 수 있도록 루프로 처리
            devices_to_try = [stream_kwargs.get('device')]
            if hasattr(self, '_fallback_devices') and self._fallback_devices:
                devices_to_try.extend(self._fallback_devices)
            
            # arecord -l로 확인된 실제 ALSA 장치도 시도
            # 주의: sounddevice는 ALSA 장치 이름 문자열을 직접 지원하지 않으므로
            # plughw: 형식을 시도하거나, PortAudio가 인식하는 장치 인덱스를 사용해야 함
            # 하지만 일단 시도해보고, 실패하면 무시
            try:
                import subprocess
                arecord_result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=2)
                if arecord_result.returncode == 0 and 'card' in arecord_result.stdout.lower():
                    # arecord -l에서 카드 정보 추출 (예: card 0: ...)
                    lines = arecord_result.stdout.strip().split('\n')
                    for line in lines:
                        if 'card' in line.lower() and 'device' in line.lower():
                            # card 0, device 0 형식 추출
                            import re
                            card_match = re.search(r'card (\d+)', line)
                            device_match = re.search(r'device (\d+)', line)
                            if card_match and device_match:
                                card_num = card_match.group(1)
                                device_num = device_match.group(1)
                                # plughw: 형식도 시도 (sounddevice가 지원할 수 있음)
                                alsa_device_plughw = f'plughw:{card_num},{device_num}'
                                if alsa_device_plughw not in [str(d) for d in devices_to_try if d is not None]:
                                    devices_to_try.append(alsa_device_plughw)
                                    print(f"   💡 ALSA 장치 추가: {alsa_device_plughw} (arecord -l에서 확인, plughw 형식)")
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                print(f"   ⚠️ arecord 확인 실패 (무시 가능): {e}")
            
            last_error = None
            for device_idx in devices_to_try:
                if device_idx is None:
                    continue
                
                try:
                    test_kwargs = stream_kwargs.copy()
                    # ALSA 장치 이름 문자열인 경우
                    # 주의: sounddevice는 hw: 형식을 지원하지 않을 수 있으므로 plughw:만 시도
                    if isinstance(device_idx, str):
                        if 'hw:' in device_idx and 'plughw:' not in device_idx:
                            # hw: 형식은 sounddevice가 지원하지 않을 수 있으므로 건너뜀
                            print(f"⚠️ 장치 [{device_idx}]는 hw: 형식입니다. sounddevice가 지원하지 않을 수 있어 건너뜁니다.")
                            if device_idx != devices_to_try[-1]:
                                continue
                        test_kwargs['device'] = device_idx
                        device_name = device_idx
                    else:
                        test_kwargs['device'] = device_idx
                        try:
                            device_info = sd.query_devices(device_idx)
                            device_name = device_info.get('name', f'인덱스 {device_idx}')
                        except:
                            device_name = f'인덱스 {device_idx}'
                    
                    print(f"🔍 장치 [{device_idx}] {device_name} 열기 시도 중...")
                    self.stream = sd.InputStream(**test_kwargs)
                    self.stream.start()
                    print(f"✅ 장치 [{device_idx}] {device_name} 열기 성공!")
                    stream_kwargs['device'] = device_idx  # 성공한 장치로 업데이트
                    break
                except Exception as stream_error:
                    last_error = stream_error
                    if isinstance(device_idx, str):
                        device_name = device_idx
                    else:
                        try:
                            device_info = sd.query_devices(device_idx) if device_idx is not None else {}
                            device_name = device_info.get('name', f'인덱스 {device_idx}')
                        except:
                            device_name = f'인덱스 {device_idx}'
                    
                    error_str = str(stream_error)
                    if 'Invalid number of channels' in error_str or 'channels' in error_str.lower():
                        print(f"⚠️ 장치 [{device_idx}] {device_name} 열기 실패: 입력 채널이 없거나 잘못되었습니다.")
                        if device_idx != devices_to_try[-1]:  # 마지막 장치가 아니면 다음 장치 시도
                            print(f"   다음 장치 시도 중...")
                            continue
                    elif 'No input device matching' in error_str or 'device matching' in error_str.lower():
                        print(f"⚠️ 장치 [{device_idx}] {device_name} 열기 실패: sounddevice가 이 장치를 인식하지 못합니다.")
                        if device_idx != devices_to_try[-1]:  # 마지막 장치가 아니면 다음 장치 시도
                            print(f"   다음 장치 시도 중...")
                            continue
                    else:
                        print(f"⚠️ 장치 [{device_idx}] {device_name} 열기 실패: {stream_error}")
                        if device_idx != devices_to_try[-1]:  # 마지막 장치가 아니면 다음 장치 시도
                            print(f"   다음 장치 시도 중...")
                            continue
                    
                    # 마지막 장치 시도 실패
                    if device_idx == devices_to_try[-1]:
                        print(f"❌ 모든 장치 열기 실패")
                        print(f"   마지막 오류: {last_error}")
                        print(f"   💡 ALSA 레벨에서 마이크 확인:")
                        print(f"      $ arecord -l")
                        print(f"      $ python3.10 check_alsa_devices.py")
                        print(f"   💡 다른 프로세스가 마이크를 점유하고 있는지 확인:")
                        print(f"      $ lsof | grep -i audio")
                        print(f"      $ fuser /dev/snd/*")
                        raise RuntimeError(f"모든 ALSA 장치를 열 수 없습니다. ALSA 레벨에서 마이크를 확인하세요.") from last_error
            
            if self.stream is None:
                raise RuntimeError("장치를 열 수 없습니다.")
            # ALSA 장치 이름인 경우 query_devices로 조회 불가
            if isinstance(device, str):
                device_name = device
            else:
                try:
                    device_info = sd.query_devices(device) if device is not None else None
                    device_name = device_info['name'] if device_info else f"인덱스 {device}"
                except:
                    device_name = f"인덱스 {device}" if device is not None else "기본 장치"
            print(f"🔊 마이크 ON (활성 상태) - 샘플레이트: {self.mic_rate}Hz, 장치: {device_name}")
        except Exception as e:
            print(f"❌ 마이크 스트림 시작 실패: {e}")
            print(f"   device_index: {device}")
            print("   사용 가능한 입력 장치 목록:")
            try:
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    if dev['max_input_channels'] > 0:
                        print(f"      [{idx}] {dev['name']} (입력 채널: {dev['max_input_channels']}, 샘플레이트: {dev['default_samplerate']}Hz)")
            except:
                pass
            raise

    def read(self, timeout=None):
        """
        큐에서 오디오 버퍼 읽기 (16000Hz로 리샘플링)
        
        Args:
            timeout: 대기 시간 (초), None이면 무한 대기
        
        Returns:
            오디오 데이터 (numpy array) 또는 None (타임아웃 시)
        """
        try:
            if timeout is not None:
                data = self.q.get(timeout=timeout)
            else:
                data = self.q.get()
            audio_48k = np.frombuffer(data, dtype=np.int16)
            
            # 48000Hz → 16000Hz 리샘플링 (3:1 비율)
            if self.mic_rate != self.stt_rate:
                num_samples_16k = int(len(audio_48k) * self.stt_rate / self.mic_rate)
                audio_16k = signal.resample(audio_48k.astype(np.float32), num_samples_16k)
                return audio_16k.astype(np.int16)
            else:
                return audio_48k
        except queue.Empty:
            return None

    def pause(self):
        """마이크 입력 일시 정지"""
        if self.stream and not self.is_paused:
            self.is_paused = True
            print("🔇 마이크 OFF (대기 상태)")

    def resume(self):
        """마이크 입력 재개"""
        if self.stream and self.is_paused:
            # 이전 데이터 제거
            while not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
            self.is_paused = False
            print("🔊 마이크 ON (활성 상태)")

    def is_active(self):
        """마이크 스트림이 활성 상태인지 확인"""
        if self.stream is None:
            return False
        # sounddevice.InputStream은 active 속성을 사용 (is_active() 메서드 없음)
        return self.stream.active and not self.is_paused

    def stop(self):
        """마이크 완전 종료"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_paused = False
        print("🔇 마이크 종료")
    
    def release(self):
        """마이크 장치 해제 (WebRTC 프로세스가 마이크를 사용할 수 있도록)"""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                print("🔇 마이크 장치 해제 (WebRTC 프로세스가 사용할 수 있음)")
            except Exception as e:
                print(f"⚠️ 마이크 해제 중 오류: {e}")
            finally:
                self.stream = None
                self.is_paused = False
    
    def acquire(self):
        """마이크 장치 재점유 (WebRTC 프로세스가 마이크를 해제한 후)"""
        if self.stream is None:
            try:
                print("🔊 마이크 장치 재점유 중...")
                self.start()  # 마이크 스트림 다시 시작
                print("✅ 마이크 장치 재점유 완료")
            except Exception as e:
                print(f"❌ 마이크 재점유 실패: {e}")
                raise
        else:
            print("ℹ️ 마이크가 이미 점유되어 있습니다.")
