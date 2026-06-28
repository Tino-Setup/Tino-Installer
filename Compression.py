import tarfile
import os

def decompress(archive_path, target_dir, compression_type, callback=None):
    """
    Decompresses an archive to the target directory.
    Supported types: 'lzma', 'gzip', 'bz2'.
    
    callback: a function that takes (current_file_index, total_files, filename)
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Archive not found: {archive_path}")
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    
    try:
        if compression_type == 'lzma':
            tar = tarfile.open(archive_path, mode='r:xz')
        elif compression_type == 'gzip':
            tar = tarfile.open(archive_path, mode='r:gz')
        elif compression_type == 'bz2':
            tar = tarfile.open(archive_path, mode='r:bz2')
        else:
            raise ValueError(f"Unsupported compression type: {compression_type}")

        with tar:
            members = tar.getmembers()
            total_files = len(members)
            
            for i, member in enumerate(members):
                member_path = os.path.join(target_dir, member.name)
                abs_target = os.path.realpath(target_dir)
                abs_member = os.path.realpath(member_path)
                if not abs_member.startswith(abs_target + os.sep) and abs_member != abs_target:
                    raise RuntimeError(f"Blocked path traversal attempt: {member.name}")
                tar.extract(member, path=target_dir, filter='data')
                if callback:
                    callback(i + 1, total_files, member.name)
                    
    except Exception as e:
        raise RuntimeError(f"Decompression failed: {e}") from e
