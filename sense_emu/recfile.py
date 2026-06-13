from .common import HEADER_REC, DATA_REC, DataRecord


def parse_recording(path):
    """Parse a .bin recording file and return a list of DataRecord namedtuples."""
    records = []
    with open(path, 'rb') as f:
        header_buf = f.read(HEADER_REC.size)
        if len(header_buf) < HEADER_REC.size:
            raise ValueError('Invalid recording file')
        magic, ver, _ = HEADER_REC.unpack(header_buf)
        if magic != b'SENSEHAT' or ver != 1:
            raise ValueError('Invalid recording file')
        while True:
            buf = f.read(DATA_REC.size)
            if not buf:
                break
            if len(buf) < DATA_REC.size:
                raise ValueError('Truncated record')
            records.append(DataRecord(*DATA_REC.unpack(buf)))
    return records


_parse_recording = parse_recording
