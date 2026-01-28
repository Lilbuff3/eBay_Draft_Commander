class QueueService:
    """Wrapper for QueueManager operations"""
    
    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        
    def get_job(self, job_id):
        return self.queue_manager.get_job_by_id(job_id)
        
    # Add pass-through methods as needed
