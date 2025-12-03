import struct

class MobiReader:
    def __init__(self, filename):
        self.filename = filename
        self.compression = 1
        self.text_length = 0
        self.record_count = 0
        self.record_size = 4096
        self.current_offset = 0
        
    def extract_text(self):
        with open(self.filename, 'rb') as f:
            header = f.read(78)
            if len(header) < 78:
                raise ValueError("Invalid file header")
                
            # PDB Header
            num_records = struct.unpack('>H', header[76:78])[0]
            
            # Record Info List
            record_info_list = []
            for _ in range(num_records):
                data = f.read(8)
                offset = struct.unpack('>L', data[:4])[0]
                record_info_list.append(offset)
                
            if not record_info_list:
                return ""

            # Read Record 0 (Mobi Header)
            f.seek(record_info_list[0])
            header_data = f.read(record_info_list[1] - record_info_list[0] if len(record_info_list) > 1 else 1024)
            
            # PalmDOC Header is at start of Record 0
            self.compression = struct.unpack('>H', header_data[0:2])[0]
            self.text_length = struct.unpack('>L', header_data[4:8])[0]
            self.record_count = struct.unpack('>H', header_data[8:10])[0]
            self.record_size = struct.unpack('>H', header_data[10:12])[0]
            
            # print(f"Compression: {self.compression}, Records: {self.record_count}")
            
            if self.compression == 17480:
                 raise ValueError("Huff/CDIC compression not supported in basic mode")
                 
            # Read Text Records
            text_content = bytearray()
            for i in range(1, self.record_count + 1):
                if i >= len(record_info_list):
                    break
                start = record_info_list[i]
                end = record_info_list[i+1] if i+1 < len(record_info_list) else None
                
                f.seek(start)
                if end:
                    chunk = f.read(end - start)
                else:
                    chunk = f.read()
                
                # Trim extra bytes if needed (some records have trailing data)
                # For now, just try to decompress
                
                if self.compression == 2:
                    text_content.extend(self.decompress_palmdoc(chunk))
                else:
                    text_content.extend(chunk)
                    
            # Try multiple encodings
            # Prioritize UTF-8 and GB18030 (common for Chinese)
            # If strict decoding fails, try with error handling BEFORE falling back to Latin1
            
            encodings_to_try = [
                ('utf-8', 'strict'),
                ('gb18030', 'strict'),
                ('utf-8', 'ignore'),  # If strict fails, try ignoring errors (likely UTF-8 with some garbage)
                ('gb18030', 'ignore'),
                ('cp1252', 'strict'),
                ('latin1', 'strict')
            ]

            for encoding, errors in encodings_to_try:
                try:
                    decoded_text = text_content.decode(encoding, errors=errors)
                    # Simple heuristic: If we used 'ignore' or 'replace', we accept it.
                    # But if we decoded as Latin1/CP1252, we might have garbage if it was actually UTF-8.
                    # Since we prioritize UTF-8/GB18030 with ignore above Latin1, this should be safer.
                    return decoded_text
                except UnicodeDecodeError:
                    continue
            
            # Fallback
            return text_content.decode('utf-8', errors='ignore')

    def decompress_palmdoc(self, data):
        output = bytearray()
        i = 0
        length = len(data)
        
        while i < length:
            byte = data[i]
            i += 1
            
            if byte == 0x00:
                output.append(byte)
            elif 0x01 <= byte <= 0x08:
                # Copy next 'byte' bytes literally
                count = byte
                if i + count > length:
                    count = length - i
                output.extend(data[i:i+count])
                i += count
            elif 0x09 <= byte <= 0x7F:
                output.append(byte)
            elif 0xC0 <= byte <= 0xFF:
                output.append(0x20)
                output.append(byte ^ 0x80)
            else: # 0x80..0xBF - LZ77 pair
                if i >= length:
                    break
                next_byte = data[i]
                i += 1
                
                pair = (byte << 8) | next_byte
                dist = (pair >> 3) & 0x07FF
                count = (pair & 0x0007) + 3
                
                for _ in range(count):
                    if dist > len(output):
                         output.append(0)
                    else:
                         output.append(output[-dist])
                         
        return output

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        try:
            reader = MobiReader(sys.argv[1])
            print(reader.extract_text()[:500])
        except Exception as e:
            print(f"Error: {e}")
